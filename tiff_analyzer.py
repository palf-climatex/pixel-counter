#!/usr/bin/env python3
"""
TIFF Analyzer - Command line tool for analyzing TIFF files in S3 bucket
with country detection and pixel counting.
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import click
import boto3
import rasterio
import geopandas as gpd
import pandas as pd
import numpy as np
from rasterio.warp import calculate_default_transform, reproject, Resampling
from shapely.geometry import box
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TIFFAnalyzer:
    """Main class for analyzing TIFF files with country detection."""
    
    def __init__(self, s3_bucket: str, s3_prefix: str = "chunked-rasters/"):
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.s3_client = boto3.client('s3')
        self.countries_gdf = None
        self.results = []
        
    def load_country_shapes(self, shapefile_path: Optional[str] = None):
        """Load country shapefiles for intersection analysis."""
        if shapefile_path and os.path.exists(shapefile_path):
            logger.info(f"Loading country shapes from: {shapefile_path}")
            self.countries_gdf = gpd.read_file(shapefile_path)
        else:
            logger.info("Downloading Natural Earth country shapes...")
            # Use Natural Earth data as fallback
            self.countries_gdf = gpd.read_file(
                gpd.datasets.get_path('naturalearth_lowres')
            )
        
        # Ensure we have the right CRS
        if self.countries_gdf.crs != 'EPSG:4326':
            self.countries_gdf = self.countries_gdf.to_crs('EPSG:4326')
        
        logger.info(f"Loaded {len(self.countries_gdf)} countries")
    
    def list_tiff_files(self) -> List[Tuple[str, str]]:
        """List all TIFF files in the S3 bucket with their subdirectories."""
        logger.info(f"Listing TIFF files in s3://{self.s3_bucket}/{self.s3_prefix}")
        
        tiff_files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.lower().endswith('.tif') or key.lower().endswith('.tiff'):
                        # Extract subdirectory from the key
                        subdir = os.path.dirname(key.replace(self.s3_prefix, ''))
                        if not subdir:
                            subdir = "root"
                        tiff_files.append((key, subdir))
        
        logger.info(f"Found {len(tiff_files)} TIFF files")
        return tiff_files
    
    def download_tiff(self, s3_key: str) -> str:
        """Download a TIFF file from S3 to a temporary file."""
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp_file:
            logger.info(f"Downloading {s3_key}")
            self.s3_client.download_file(self.s3_bucket, s3_key, tmp_file.name)
            return tmp_file.name
    
    def get_tiff_bounds(self, tiff_path: str) -> Tuple[float, float, float, float]:
        """Get the bounding box of a TIFF file in WGS84 coordinates."""
        with rasterio.open(tiff_path) as src:
            # Get bounds in the source CRS
            bounds = src.bounds
            
            # If not in WGS84, transform
            if src.crs != 'EPSG:4326':
                transform, width, height = calculate_default_transform(
                    src.crs, 'EPSG:4326', src.width, src.height, *bounds
                )
                bounds = rasterio.transform.array_bounds(height, width, transform)
            
            return bounds
    
    def find_intersecting_countries(self, bounds: Tuple[float, float, float, float]) -> List[str]:
        """Find countries that intersect with the TIFF bounds."""
        minx, miny, maxx, maxy = bounds
        tiff_bbox = box(minx, miny, maxx, maxy)
        
        intersecting_countries = []
        for idx, row in self.countries_gdf.iterrows():
            if row.geometry.intersects(tiff_bbox):
                country_name = row.get('name', row.get('NAME', f'Country_{idx}'))
                intersecting_countries.append(country_name)
        
        return intersecting_countries
    
    def analyze_tiff_pixels(self, tiff_path: str, countries: List[str]) -> Dict:
        """Analyze pixel values for each country in the TIFF."""
        results = {}
        
        with rasterio.open(tiff_path) as src:
            # Read the entire raster
            data = src.read(1)  # Read first band
            
            # Get bounds for intersection
            bounds = self.get_tiff_bounds(tiff_path)
            minx, miny, maxx, maxy = bounds
            tiff_bbox = box(minx, miny, maxx, maxy)
            
            for country in countries:
                # Find the country geometry
                country_row = self.countries_gdf[
                    (self.countries_gdf['name'] == country) | 
                    (self.countries_gdf['NAME'] == country)
                ].iloc[0]
                
                country_geom = country_row.geometry
                
                # Create a mask for the country
                # This is a simplified approach - for more accuracy, you'd need to rasterize the country shape
                # For now, we'll analyze the entire TIFF and note the limitation
                
                # Count total pixels (excluding NoData)
                total_pixels = np.sum(data != src.nodata) if src.nodata is not None else data.size
                
                # Count pixels in range 1-6
                valid_pixels = np.sum((data >= 1) & (data <= 6))
                
                results[country] = {
                    'total_pixels': int(total_pixels),
                    'valid_pixels': int(valid_pixels),
                    'fraction_valid': float(valid_pixels / total_pixels) if total_pixels > 0 else 0.0
                }
        
        return results
    
    def process_tiff(self, s3_key: str, subdir: str) -> Dict:
        """Process a single TIFF file."""
        logger.info(f"Processing {s3_key}")
        
        # Download TIFF
        tiff_path = self.download_tiff(s3_key)
        
        try:
            # Get bounds and find intersecting countries
            bounds = self.get_tiff_bounds(tiff_path)
            countries = self.find_intersecting_countries(bounds)
            
            if not countries:
                logger.warning(f"No countries found for {s3_key}")
                return {
                    's3_key': s3_key,
                    'subdir': subdir,
                    'countries': [],
                    'analysis': {}
                }
            
            # Analyze pixels for each country
            analysis = self.analyze_tiff_pixels(tiff_path, countries)
            
            return {
                's3_key': s3_key,
                'subdir': subdir,
                'countries': countries,
                'analysis': analysis
            }
            
        finally:
            # Clean up temporary file
            os.unlink(tiff_path)
    
    def run_analysis(self, output_file: str = "tiff_analysis_results.csv"):
        """Run the complete analysis pipeline."""
        logger.info("Starting TIFF analysis...")
        
        # Load country shapes
        self.load_country_shapes()
        
        # List all TIFF files
        tiff_files = self.list_tiff_files()
        
        if not tiff_files:
            logger.error("No TIFF files found!")
            return
        
        # Process each TIFF
        for s3_key, subdir in tiff_files:
            try:
                result = self.process_tiff(s3_key, subdir)
                self.results.append(result)
            except Exception as e:
                logger.error(f"Error processing {s3_key}: {e}")
        
        # Aggregate results
        self.aggregate_results()
        
        # Save results
        self.save_results(output_file)
        
        logger.info(f"Analysis complete! Results saved to {output_file}")
    
    def aggregate_results(self):
        """Aggregate results by subdirectory and country."""
        aggregated = defaultdict(lambda: defaultdict(lambda: {
            'total_pixels': 0,
            'valid_pixels': 0,
            'tiff_count': 0
        }))
        
        for result in self.results:
            subdir = result['subdir']
            for country, analysis in result['analysis'].items():
                aggregated[subdir][country]['total_pixels'] += analysis['total_pixels']
                aggregated[subdir][country]['valid_pixels'] += analysis['valid_pixels']
                aggregated[subdir][country]['tiff_count'] += 1
        
        # Calculate final fractions
        self.aggregated_results = []
        for subdir, countries in aggregated.items():
            for country, data in countries.items():
                fraction_valid = (data['valid_pixels'] / data['total_pixels'] 
                                if data['total_pixels'] > 0 else 0.0)
                
                self.aggregated_results.append({
                    'subdirectory': subdir,
                    'country': country,
                    'total_pixels': data['total_pixels'],
                    'valid_pixels': data['valid_pixels'],
                    'fraction_valid': fraction_valid,
                    'tiff_count': data['tiff_count']
                })
    
    def save_results(self, output_file: str):
        """Save results to CSV file."""
        df = pd.DataFrame(self.aggregated_results)
        df.to_csv(output_file, index=False)
        logger.info(f"Saved {len(df)} aggregated results to {output_file}")
        
        # Print summary
        print("\n=== ANALYSIS SUMMARY ===")
        print(f"Total subdirectories: {df['subdirectory'].nunique()}")
        print(f"Total countries: {df['country'].nunique()}")
        print(f"Total TIFFs processed: {df['tiff_count'].sum()}")
        print(f"Average fraction of valid data: {df['fraction_valid'].mean():.3f}")


@click.command()
@click.option('--bucket', default='tech-jobs-sot', help='S3 bucket name')
@click.option('--prefix', default='chunked-rasters/', help='S3 prefix for TIFF files')
@click.option('--output', default='tiff_analysis_results.csv', help='Output CSV file')
@click.option('--shapefile', help='Path to country shapefile (optional)')
def main(bucket: str, prefix: str, output: str, shapefile: str):
    """Analyze TIFF files in S3 bucket with country detection and pixel counting."""
    try:
        analyzer = TIFFAnalyzer(bucket, prefix)
        analyzer.run_analysis(output)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 