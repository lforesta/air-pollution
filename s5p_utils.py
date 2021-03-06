import os
import subprocess
from osgeo import gdal
import numpy as np


def write_s5p_tif(in_filepath, variables, output_folder, EPSG_code="4326", spatial_res=[]):
    """
    Write specified variables of S5p NETCDF file to a georeferenced GTiff file 
    in Pseudo-Mercator with spatial resolution 3500m x 7000m.
    
    Parameters
    ----------
    in_filepath: str
        full filepath to S5p NETCDF file (.nc)
    variables: list of str
        list of variables in the S5p NETCDF file that will be written to GTiff files
    EPSG_code: str
        EPSG code of desired projection, default is 3857 (Pseudo-Mercator)
    spatial_res: list of float
        X and Y spatial resolution (sampling) in degrees or meters according to the chosen projection
        Defaults to 3500m x 7000m (or degree equivalent scaled by mean latitude)
    
    """
    
    kwargs = {}
    kwargs['EPSG_code'] = EPSG_code
    kwargs['spatial_res'] = spatial_res

    # Create vrt files for latitude and longitude variables
    geo_params = {}
    geo_params['outputSRS'] = f"EPSG:{EPSG_code}"
    gdal.Translate("lat.vrt", f'HDF5:"{in_filepath}"://PRODUCT/latitude', **geo_params)
    lat_ds = gdal.Open("lat.vrt")
    lats = lat_ds.ReadAsArray()
    gdal.Translate("lon.vrt", gdal.Open(f'HDF5:"{in_filepath}"://PRODUCT/longitude'), **geo_params)
    
    ds = gdal.Open(in_filepath)
    md = ds.GetMetadata()
    
    data_var = "temp_s5p.tif"
    mask_var = "qa_value.tif"
    output_file = generate_out_filepath(in_filepath, output_folder, ".tif")

    for variable in variables:
        # Georeference variable datset
        write_var_to_tif(data_var, in_filepath, variable, "lon.vrt", "lat.vrt", lat_ds,
                      **kwargs)
        # Georeference quality_value datset
        write_var_to_tif(mask_var, in_filepath, "qa_value", "lon.vrt", "lat.vrt", lat_ds,
                      **kwargs)
        # Apply quality mask to variable dataset
        write_masked_data(output_file, data_var, mask_var, mask_threshold=75)
        
        # Clean
        os.remove(data_var)
        os.remove(data_var.split('.')[0] + '_.vrt')
        os.remove(mask_var)
        os.remove(mask_var.split('.')[0] + '_.vrt')
    
    # Remove vrt files
    os.remove('lon.vrt')
    os.remove('lat.vrt')


def write_var_to_tif(out_filepath, in_filepath, variable, lon_file, lat_file, ds, **kwargs):
    """
    
    """
    
    vrt_filepath = out_filepath.split('.')[0] + '_.vrt'
    
    with open(vrt_filepath, "w") as text_file:
        text_file.write(f"""
<VRTDataset rasterXSize="{ds.RasterXSize}" rasterYSize="{ds.RasterYSize}">
    <metadata domain="GEOLOCATION">
        <mdi key="X_DATASET">{lon_file}</mdi>
        <mdi key="X_BAND">1</mdi>
        <mdi key="Y_DATASET">{lat_file}</mdi>
        <mdi key="Y_BAND">1</mdi>
        <mdi key="PIXEL_OFFSET">0</mdi>
        <mdi key="LINE_OFFSET">0</mdi>
        <mdi key="PIXEL_STEP">1</mdi>
        <mdi key="LINE_STEP">1</mdi>
    </metadata> 
    <VRTRasterBand band="1" datatype="Float32">
        <SimpleSource>
            <SourceFilename relativeToVRT="0">HDF5:{in_filepath}://PRODUCT/{variable}</SourceFilename>
            <SourceBand>1</SourceBand>
            <SourceProperties RasterXSize="{ds.RasterXSize}" RasterYSize="{ds.RasterYSize}" DataType="Float32" BlockXSize="{ds.RasterXSize}" BlockYSize="{ds.RasterYSize}" />
            <SrcRect xOff="0" yOff="0" xSize="{ds.RasterXSize}" ySize="{ds.RasterYSize}" />
            <DstRect xOff="0" yOff="0" xSize="{ds.RasterXSize}" ySize="{ds.RasterYSize}" />
        </SimpleSource>
    </VRTRasterBand>
</VRTDataset>
""")
    
    # Add georeferencing to vrt file
    georef_data(out_filepath, vrt_filepath, vrt=False, **kwargs)
    

def write_masked_data(out_filepath, data_file, mask_file, mask_threshold=75):
    """
    
    """

    data_ds = gdal.Open(data_file)
    data = data_ds.ReadAsArray()
    mask = gdal.Open(mask_file).ReadAsArray()
    data[mask <= mask_threshold] = np.nan
    
    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(
        out_filepath,
        data_ds.RasterXSize,
        data_ds.RasterYSize,
        1,
        gdal.GDT_Float32, )

    dataset.SetGeoTransform(data_ds.GetGeoTransform())  
    dataset.SetProjection(data_ds.GetProjectionRef())
    dataset.GetRasterBand(1).WriteArray(data)
    dataset.FlushCache()  # Write to disk.


def georef_data(out_filepath, in_filepath, vrt, EPSG_code, spatial_res):
    """
    
    """
    
    params = {}
    #params['geoloc'] = True
    #params['srcNodata'] = float(md[f"PRODUCT_{variable}__FillValue"])
    params['dstNodata'] = -9999
    params['dstSRS'] = f"EPSG:{EPSG_code}"
    if vrt:
        params["format"] = "VRT"
        #ext = ".vrt"
        out_filepath = out_filepath.replace('.tif', '.vrt')
    else:
        params["format"] = "Gtiff"
        #ext = ".tif"
        out_filepath = out_filepath.replace('.vrt', '.tif')
    if not spatial_res:
        if EPSG_code == "4326":
            params['xRes'] = 0.06288  # equivalent to 7000 meters
            params['yRes'] = 0.06288  # equivalent to 7000 meters
        else:
            params['xRes'] = 7000  # meters
            params['xRes'] = 7000  # meters
    else:
        params['xRes'] = spatial_res[0]
        params['xRes'] = spatial_res[1]

    #out_filepath = generate_out_filepath(in_filepath, output_folder, ext)
    gdal.Warp(out_filepath, in_filepath, **params)
    
            

def generate_out_filepath(in_filepath, output_folder, ext):
    """
    
    
    ext: '.tif', '.vrt'
    
    """
    
    filename = in_filepath.split(os.path.sep)[-1]
    var_name_short = filename[13:20].replace('_','')
    timestamp = filename[20:35]
    return output_folder + os.path.sep + var_name_short + '_' + timestamp + ext
    

def merge_rasters(in_filenames, output_filename):
    """
    
    """
    
    cmd_gdal_merge = " ".join([
                                'gdal_merge.py', '-init 255 -o', output_filename, \
                                '-n 9999' \
                                ] + \
                                ['"%s"' % in_filename for in_filename in in_filenames])
    subprocess.check_output(cmd_gdal_merge, shell=True)
