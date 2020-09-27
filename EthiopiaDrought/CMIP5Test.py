from osgeo import gdal,osr,ogr
import os
import glob
import numpy as np
import pandas as pd
import h5py
from netCDF4 import Dataset
from dateutil import rrule
from datetime import *
from matplotlib import cm
from matplotlib import pyplot as plt
from scipy import signal
def clipbyshp(input_raster,output_raster,input_shape, dstNodata=-9999):
    """
    :param input_raster: the raster data being processed later
    :param output_raster: the clipped datas' savepaths
    :param input_shape: the shape defining the extent
    :return: none
    """
    ds = gdal.Warp(output_raster,
                   input_raster,
                   format='GTiff',
                   cutlineDSName=input_shape,  # or any other file format
                   # cutlineDSName=None,
                   # cutlineWhere="FIELD = 'whatever'",
                   # optionally you can filter your cutline (shapefile) based on attribute values
                   cropToCutline=True,
                   dstNodata=dstNodata)  # select the no data value you like
    ds = None

def write_Img(data, path, proj, geotrans,im_width, im_heigth,im_bands=1, dtype=gdal.GDT_Float32):

    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, im_width, im_heigth, im_bands, dtype)

    dataset.SetGeoTransform(geotrans)

    dataset.SetProjection(str(proj))
    if im_bands ==1:
        dataset.GetRasterBand(1).WriteArray(data)
    else:
        for id in range(im_bands):
            # print("**********")
            dataset.GetRasterBand(id+1).WriteArray(data[:,:,id])
    del dataset





def monthComp(cmipclippeddirectory,outputdirectory,year,month):
    refpath = r"D:\Cornell\EthiopianDrought\CMIP5Daily\cmip5_20060101.tif"
    reference = gdal.Open(refpath)
    geotrans = reference.GetGeoTransform()
    proj = reference.GetProjection()

    start = datetime.strptime("-".join([str(2006), str(6).zfill(2), "01"]), "%Y-%m-%d").date()
    stop = datetime.strptime("-".join([str(2020), str(9).zfill(2), "30"]), "%Y-%m-%d").date()
    bandNum = 0
    axisTime = []
    for dt in (rrule.rrule(rrule.DAILY, interval=1, dtstart=start, until=stop)):

        chirps_file = os.path.join(cmipclippeddirectory,
                                   "cmip5_{}{}{}.tif".format(str(dt.year), str(dt.month).zfill(2),
                                                                     str(dt.day).zfill(2)))
        if os.path.exists(chirps_file):
            bandNum += 1
    print("bandNum", bandNum)
    mask = np.zeros((143, 95))
    multidarr = np.zeros((143, 95, bandNum))
    band_id = 0

    for dt in (rrule.rrule(rrule.DAILY, interval=1, dtstart=start, until=stop)):
        print(dt)
        chirps_file = os.path.join(cmipclippeddirectory,
                                   "cmip5_{}{}{}.tif".format(str(dt.year), str(dt.month).zfill(2),
                                                                     str(dt.day).zfill(2)))
        print(chirps_file)
        chirps = gdal.Open(chirps_file).ReadAsArray()

        multidarr[:, :, band_id] = chirps
        mask[chirps == -9999] += 1
        band_id += 1
        axisTime.append([dt.year, dt.month])

    print(multidarr[3,2,:].mean())
    compdata = multidarr.mean(axis=2)
    compdata[mask >=1] = -9999
    print(compdata[3,2])
    path = os.path.join(outputdirectory,r"cmip5_long_{}.tif".format(year))
    write_Img(compdata, path, proj, geotrans, 95, 143, im_bands=1, dtype=gdal.GDT_Float32)

for year in range(2006,2007):
    for month in range(1,13):
        monthComp(r"D:\Cornell\EthiopianDrought\CMIP5Daily", r"D:\Cornell\EthiopianDrought\Test\CMIP5Season",
                  year, month)