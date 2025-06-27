"""
Configuration settings for the TIFF Analyzer.
"""

# S3 Configuration
DEFAULT_S3_BUCKET = "tech-jobs-sot"
DEFAULT_S3_PREFIX = "chunked-rasters/"

# Data Validation
VALID_PIXEL_MIN = 1
VALID_PIXEL_MAX = 6

# Output Configuration
DEFAULT_OUTPUT_FILE = "tiff_analysis_results.csv"
IMPROVED_OUTPUT_FILE = "improved_tiff_analysis_results.csv"

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Processing Configuration
CHUNK_SIZE = 1024  # For potential future chunked processing
MAX_WORKERS = 1    # For potential future parallel processing

# Geographic Configuration
DEFAULT_CRS = "EPSG:4326"  # WGS84
NATURAL_EARTH_DATASET = "naturalearth_lowres"

# File Extensions
TIFF_EXTENSIONS = ['.tif', '.tiff']

# Temporary File Configuration
TEMP_FILE_SUFFIX = '.tif'
TEMP_FILE_DELETE = True 