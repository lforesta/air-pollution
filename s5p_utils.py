import os
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

    # Create vrt files for latitude and longitude variables
    geo_params = {}
    geo_params['outputSRS'] = f"EPSG:{EPSG_code}"
    gdal.Translate("lat.vrt", f'HDF5:"{in_filepath}"://PRODUCT/latitude', **geo_params)
    lat_ds = gdal.Open("lat.vrt")
    lats = lat_ds.ReadAsArray()
    gdal.Translate("lon.vrt", gdal.Open(f'HDF5:"{in_filepath}"://PRODUCT/longitude'), **geo_params)
    
    ds = gdal.Open(in_filepath)
    md = ds.GetMetadata()

    for variable in variables:
        write_s5p_vrt("temp_s5p.vrt", in_filepath, variable, "lon.vrt", "lat.vrt", lat_ds)

        # Burn to disk in GTiff
        params = {}
        params['geoloc'] = True
        params['srcNodata'] = float(md[f"PRODUCT_{variable}__FillValue"])
        params['dstNodata'] = 9999
        params['dstSRS'] = f"EPSG:{EPSG_code}"
        params["format"] = "GTiff"
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

        out_filepath = generate_out_filepath(in_filepath, output_folder)
        gdal.Warp(out_filepath, "temp_s5p.vrt", **params)
    
    # Remove vrt files
    os.remove('lon.vrt')
    os.remove('lat.vrt')


def write_s5p_vrt(out_filepath, in_filepath, variable, lon_file, lat_file, ds):
    """
    
    """
    
    with open(out_filepath, "w") as text_file:
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
            

def generate_out_filepath(in_filepath, output_folder):
    """
    
    """
    
    filename = in_filepath.split(os.path.sep)[-1]
    var_name_short = filename[13:20].replace('_','')
    timestamp = filename[20:35]
    return output_folder + os.path.sep + var_name_short + '_' + timestamp + '.tif'
