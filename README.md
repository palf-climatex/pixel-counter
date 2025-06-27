# TIFF Analyzer

A command line tool for analyzing TIFF files in S3 buckets with country detection and pixel counting. The tool finds all TIFF files in a specified S3 bucket, determines which countries intersect with each tile, and calculates pixel statistics for each country.

## Features

- **S3 Integration**: Lists and downloads TIFF files from S3 buckets
- **Country Detection**: Uses Natural Earth country boundaries to determine which countries intersect with each TIFF
- **Accurate Pixel Counting**: Rasterizes country shapes to accurately count pixels within country boundaries
- **Data Validation**: Counts pixels in the range 1-6 (valid data) vs total pixels
- **Aggregation**: Groups results by subdirectory and country, calculating fraction of valid data
- **CSV Output**: Saves results in a structured CSV format for further analysis

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd pixel-counter
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials** (if not already configured):
   ```bash
   aws configure
   ```

## Usage

### Basic Usage

Run the improved analyzer (recommended):

```bash
python tiff_analyzer_improved.py
```

This will:
- Use the default S3 bucket `tech-jobs-sot`
- Look for TIFFs in the `chunked-rasters/` prefix
- Save results to `improved_tiff_analysis_results.csv`

### Advanced Usage

```bash
python tiff_analyzer_improved.py \
    --bucket your-bucket-name \
    --prefix your/prefix/path/ \
    --output results.csv \
    --shapefile /path/to/country/shapefile.shp \
    --limit 10
```

### Command Line Options

- `--bucket`: S3 bucket name (default: `tech-jobs-sot`)
- `--prefix`: S3 prefix for TIFF files (default: `chunked-rasters/`)
- `--output`: Output CSV file path (default: `improved_tiff_analysis_results.csv`)
- `--shapefile`: Path to custom country shapefile (optional, uses Natural Earth data by default)
- `--limit`: Limit number of TIFFs to process (useful for testing)

### Example Output

The tool generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `subdirectory` | The subdirectory containing the TIFF |
| `country` | Country name |
| `total_pixels` | Total number of pixels in the country |
| `valid_pixels` | Number of pixels with values 1-6 |
| `fraction_valid` | Fraction of valid data (valid_pixels / total_pixels) |
| `tiff_count` | Number of TIFF files contributing to this result |

## How It Works

1. **File Discovery**: Lists all `.tif` and `.tiff` files in the specified S3 bucket and prefix
2. **Country Loading**: Loads country boundaries from Natural Earth data (or custom shapefile)
3. **Intersection Detection**: For each TIFF, determines which countries intersect with its bounding box
4. **Pixel Analysis**: For each intersecting country:
   - Rasterizes the country geometry to create a mask
   - Applies the mask to the TIFF data
   - Counts total pixels and pixels in range 1-6
5. **Aggregation**: Groups results by subdirectory and country, calculating overall statistics
6. **Output**: Saves aggregated results to CSV

## Performance Considerations

- **Memory Usage**: Each TIFF is downloaded to a temporary file and processed in memory
- **Processing Time**: Depends on the number and size of TIFF files
- **Testing**: Use the `--limit` option to test with a subset of files
- **Parallel Processing**: The current implementation processes files sequentially

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure your AWS credentials are configured and have access to the S3 bucket
2. **Memory Errors**: For large TIFFs, consider processing in chunks or using a machine with more RAM
3. **CRS Issues**: The tool automatically handles coordinate reference system transformations
4. **No Countries Found**: Check if your TIFFs are in a geographic area covered by the country boundaries

### Logging

The tool provides detailed logging output. Check the console output for:
- Number of TIFF files found
- Processing progress
- Any errors or warnings
- Final summary statistics

## Dependencies

- `boto3`: AWS S3 access
- `rasterio`: TIFF file reading and processing
- `geopandas`: Geographic data handling
- `pandas`: Data manipulation and CSV output
- `numpy`: Numerical operations
- `shapely`: Geometric operations
- `click`: Command line interface

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here] 