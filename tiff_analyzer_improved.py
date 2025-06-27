#!/usr/bin/env python3
"""
Improved TIFF Analyzer - Command line tool for analyzing TIFF files in S3 bucket
with accurate country detection and pixel counting using rasterized country masks.
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
from rasterio.features import rasterize
from shapely.geometry import box
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ImprovedTIFFAnalyzer:
    """Improved TIFF analyzer with accurate country mask rasterization."""
    
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
    
    def find_intersecting_countries(self, bounds: Tuple[float, float, float, float]) -> List[Tuple[str, object]]:
        """Find countries that intersect with the TIFF bounds."""
        minx, miny, maxx, maxy = bounds
        tiff_bbox = box(minx, miny, maxx, maxy)
        
        intersecting_countries = []
        for idx, row in self.countries_gdf.iterrows():
            if row.geometry.intersects(tiff_bbox):
                country_name = row.get('name', row.get('NAME', f'Country_{idx}'))
                intersecting_countries.append((country_name, row.geometry))
        
        return intersecting_countries
    
    def analyze_tiff_pixels_with_masks(self, tiff_path: str, countries: List[Tuple[str, object]]) -> Dict:
        """Analyze pixel values for each country using rasterized masks."""
        results = {}
        
        with rasterio.open(tiff_path) as src:
            # Read the raster data
            data = src.read(1)
            
            # Get the transform and shape for rasterization
            transform = src.transform
            shape = src.shape
            
            for country_name, country_geom in countries:
                try:
                    # Rasterize the country geometry to create a mask
                    country_mask = rasterize(
                        [country_geom],
                        out_shape=shape,
                        transform=transform,
                        fill=0,
                        dtype=np.uint8
                    )
                    
                    # Apply the mask to get pixels within the country
                    masked_data = data[country_mask == 1]
                    
                    if len(masked_data) == 0:
                        # No pixels in this country
                        results[country_name] = {
                            'total_pixels': 0,
                            'valid_pixels': 0,
                            'fraction_valid': 0.0
                        }
                        continue
                    
                    # Count total pixels (excluding NoData)
                    if src.nodata is not None:
                        total_pixels = np.sum(masked_data != src.nodata)
                    else:
                        total_pixels = len(masked_data)
                    
                    # Count pixels in range 1-6
                    valid_pixels = np.sum((masked_data >= 1) & (masked_data <= 6))
                    
                    results[country_name] = {
                        'total_pixels': int(total_pixels),
                        'valid_pixels': int(valid_pixels),
                        'fraction_valid': float(valid_pixels / total_pixels) if total_pixels > 0 else 0.0
                    }
                    
                except Exception as e:
                    logger.warning(f"Error processing country {country_name}: {e}")
                    results[country_name] = {
                        'total_pixels': 0,
                        'valid_pixels': 0,
                        'fraction_valid': 0.0
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
            
            # Analyze pixels for each country using rasterized masks
            analysis = self.analyze_tiff_pixels_with_masks(tiff_path, countries)
            
            return {
                's3_key': s3_key,
                'subdir': subdir,
                'countries': [country[0] for country in countries],
                'analysis': analysis
            }
            
        finally:
            # Clean up temporary file
            os.unlink(tiff_path)
    
    def run_analysis(self, output_file: str = "improved_tiff_analysis_results.csv"):
        """Run the complete analysis pipeline."""
        logger.info("Starting improved TIFF analysis...")
        
        # Load country shapes
        self.load_country_shapes()
        
        # List all TIFF files
        tiff_files = self.list_tiff_files()
        
        if not tiff_files:
            logger.error("No TIFF files found!")
            return
        
        # Process each TIFF
        for i, (s3_key, subdir) in enumerate(tiff_files, 1):
            try:
                logger.info(f"Processing TIFF {i}/{len(tiff_files)}: {s3_key}")
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
        print("\n=== IMPROVED ANALYSIS SUMMARY ===")
        print(f"Total subdirectories: {df['subdirectory'].nunique()}")
        print(f"Total countries: {df['country'].nunique()}")
        print(f"Total TIFFs processed: {df['tiff_count'].sum()}")
        print(f"Average fraction of valid data: {df['fraction_valid'].mean():.3f}")
        
        # Show top countries by pixel count
        print("\nTop 10 countries by total pixels:")
        top_countries = df.groupby('country')['total_pixels'].sum().sort_values(ascending=False).head(10)
        for country, pixels in top_countries.items():
            print(f"  {country}: {pixels:,} pixels")


@click.command()
@click.option('--bucket', default='tech-jobs-sot', help='S3 bucket name')
@click.option('--prefix', default='chunked-rasters/', help='S3 prefix for TIFF files')
@click.option('--output', default='improved_tiff_analysis_results.csv', help='Output CSV file')
@click.option('--shapefile', help='Path to country shapefile (optional)')
@click.option('--limit', type=int, help='Limit number of TIFFs to process (for testing)')
def main(bucket: str, prefix: str, output: str, shapefile: str, limit: int):
    """Analyze TIFF files in S3 bucket with accurate country detection and pixel counting."""
    try:
        analyzer = ImprovedTIFFAnalyzer(bucket, prefix)
        
        if limit:
            logger.info(f"Limiting analysis to {limit} TIFF files for testing")
            # Modify the list_tiff_files method to respect the limit
            original_method = analyzer.list_tiff_files
            analyzer.list_tiff_files = lambda: original_method()[:limit]
        
        analyzer.run_analysis(output)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 