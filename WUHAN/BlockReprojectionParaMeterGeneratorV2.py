from osgeo import gdal,osr,ogr
import numpy as np
import os
import time
from multiprocessing import Pool
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





def BckParameterGenerator(Parameters):
    SrcEPSG, TargetEPSG, pixel_spacing, ulx, uly, x_size,y_size = Parameters
    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(SrcEPSG)
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(TargetEPSG)
    ct = osr.CoordinateTransformation(src_srs, target_srs)
    ct_inv = osr.CoordinateTransformation(target_srs,src_srs)

    #  50 度四点
    p1x, p1y = ulx, uly
    p2x, p2y = p1x + x_size *pixel_spacing, p1y
    p3x, p3y = p2x, p2y - y_size*pixel_spacing
    p4x, p4y = p1x, p3y

    # 投影后顶点坐标
    rep1x, rep1y = ct.TransformPoint(p1x, p1y)[0:2]
    rep2x, rep2y = ct.TransformPoint(p2x, p2y)[0:2]
    rep3x, rep3y = ct.TransformPoint(p3x, p3y)[0:2]
    rep4x, rep4y = ct.TransformPoint(p4x, p4y)[0:2]

    minX = min(rep1x, rep4x)
    maxX = max(rep2x, rep3x)
    minY = min(rep3y, rep4y)
    maxY = max(rep1y, rep2y)

    # 49度带的对角坐标
    ulx = int(minX / pixel_spacing) * pixel_spacing
    uly = int(np.ceil((maxY) / pixel_spacing)) * pixel_spacing
    lrx = int(np.ceil((maxX) / pixel_spacing)) * pixel_spacing
    lry = int(minY / pixel_spacing) * pixel_spacing
    # print(ulx,uly)
    # 49度带的宽高
    Width = int((lrx - ulx) / pixel_spacing)
    Heigth = int((uly - lry) / pixel_spacing)
    # print("W H", Width, Heigth)

    # 遍历重投影后外接矩形
    WD1 = ulx + np.repeat(a=[np.arange(Width)], repeats=Heigth, axis=0).flatten() * pixel_spacing + 0.5 * pixel_spacing
    HD1 = uly - np.repeat(a=np.arange(Heigth), repeats=Width) * pixel_spacing - 0.5 * pixel_spacing
    Pair = np.column_stack((WD1, HD1))

    # 49度带转50度
    Pair = ct_inv.TransformPoints(Pair)
    Pair = np.array(Pair).reshape(Heigth, Width, 3)
    PairX = Pair[:, :, 0]
    PairY = Pair[:, :, 1] # 外接矩形的每个像素保存了在邻带的值
    del Pair
    # 判断是否在外面
    mask = (PairX < p1x) | (PairX >= p2x) | (PairY > p1y) | (PairY <= p4y)

    PairX[mask] = 0
    PairY[mask] = 0
    Valid = PairX != 0 # 只保留落在邻带中的数据
    del mask
    COL = np.floor((PairX - p1x) / pixel_spacing).astype(np.int32)
    ROW = np.floor((p1y - PairY) / pixel_spacing).astype(np.int32)
    del PairX
    del PairY
    ECord = WD1.reshape(Heigth, Width)
    NCord = HD1.reshape(Heigth, Width)
    del WD1
    del HD1
    Fill_value = 20000
    ParaMeterX = np.ones(shape=(y_size, x_size), dtype=np.float)*Fill_value
    ParaMeterY = np.ones(shape=(y_size, x_size), dtype=np.float)*Fill_value

    ValidCOL = COL[Valid]
    ValidROW = ROW[Valid]
    del COL
    del ROW
    ValidRC = ValidCOL + ValidROW * x_size

    np.put(a=ParaMeterX, ind=ValidRC, v=ECord[Valid])
    np.put(a=ParaMeterY, ind=ValidRC, v=NCord[Valid])  # 50里存放了49带
    del ECord
    del NCord
    del ValidCOL
    del ValidROW
    del ValidRC

    # 50带投49
    EpValidCOL = np.floor((ParaMeterX[ParaMeterX != Fill_value] - ulx) / pixel_spacing).astype(np.int)
    EpValidROW = np.floor((uly - ParaMeterY[ParaMeterY !=Fill_value]) / pixel_spacing).astype(np.int)
    EpValidRC = EpValidCOL + EpValidROW * Width
    del EpValidROW
    del EpValidCOL
    Value = np.ones_like(EpValidRC,dtype=np.float)
    RepImg = np.ones((Heigth, Width))*Fill_value
    np.put(a=RepImg,ind=EpValidRC,v=Value) # 将50 范围写入49
    del Value
    del EpValidRC

    # 空白部分的值。
    mROW,mCOL = np.where(RepImg == Fill_value)
    del RepImg
    mECord = ulx + mCOL*pixel_spacing + 0.5*pixel_spacing
    mNCord = uly - mROW*pixel_spacing - 0.5*pixel_spacing
    del mROW
    del mCOL
    mPair = np.column_stack((mECord, mNCord))
    mXY = ct_inv.TransformPoints(mPair) # 转会50
    del mPair

    mXY = np.array(mXY).reshape(len(mXY),3)
    EmptyX,EmptyY = mXY[:,0],mXY[:,1]
    del mXY
    mask = (EmptyX < p1x) | (EmptyX >= p2x) | (EmptyY > p1y) | (EmptyY <= p4y)
    mvalid = mask == False
    del mask
    mValidCOL = np.floor((EmptyX[mvalid]-p1x)/pixel_spacing).astype(np.int)
    mValidROW = np.floor((p1y - EmptyY[mvalid])/pixel_spacing).astype(np.int)
    mValidRC = mValidCOL + mValidROW * x_size
    del mValidCOL
    del mValidROW
    ParaMeterXGapFiller = np.ones(shape=(y_size, x_size), dtype=np.float)*Fill_value
    ParaMeterYGapFiller= np.ones(shape=(y_size, x_size), dtype=np.float)*Fill_value
    #
    np.put(a=ParaMeterXGapFiller, ind=mValidRC, v=mECord[mvalid])
    np.put(a=ParaMeterYGapFiller, ind=mValidRC, v=mNCord[mvalid])


    del mValidRC
    del mECord
    del mNCord
    del mvalid
    return [ParaMeterX,ParaMeterY,ParaMeterXGapFiller,ParaMeterYGapFiller]


# ParameterGenerator(ImgPath,32650,32649,r'C:\Users\zmhwh\Desktop\Temp')
# ParaMeterX,ParaMeterY,ParaMeterXGapFiller,ParaMeterYGapFiller=ParameterGenerator([32650,32649,10,199980.0, 3400020.0,1830,1830])
# SrcEPSG, TargetEPSG, pixel_spacing, ulx, uly, x_size,y_size = Parameters
# [[199980.0, 3400020.0], [218280.0, 3400020.0], [218280.0, 3381720.0], [199980.0, 3381720.0]]

if __name__ == '__main__':
    S2TileGranule = r'C:\Users\zmhwh\Desktop\S2A_T49RGP'
    S2TileGranule = os.path.join(S2TileGranule,r'T49RGP_20190105T030111_B04_10m.jp2')
    st = time.time()
    g = gdal.Open(S2TileGranule)
    geo_t = g.GetGeoTransform()
    proj = g.GetProjection()
    x_size = g.RasterXSize  # Raster xsize
    y_size = g.RasterYSize  # Raster ysize
    pixel_spacing = geo_t[1]
    block_step = 1830
    block_num = int(x_size/1830)
    block = []
    OutPutDir = r'C:\Users\zmhwh\Desktop\Temp'
    # 必填
    TileName = 'T49RGP'
    ToTileName = '50N'
    SrcEPSG, TargetEPSG = 32649,32650
    check = osr.SpatialReference()
    check.ImportFromWkt(str(proj))
    check.AutoIdentifyEPSG()
    EPSG = int(check.GetAttrValue("AUTHORITY", 1))
    assert SrcEPSG == EPSG,"epsg no match"
    assert EPSG != TargetEPSG,'same epsg'


    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(SrcEPSG)
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(TargetEPSG)
    ct = osr.CoordinateTransformation(src_srs, target_srs)

    #  50 度四点
    p1x, p1y = geo_t[0], geo_t[3]
    p2x, p2y = p1x + x_size * pixel_spacing, p1y
    p3x, p3y = p2x, p2y - y_size * pixel_spacing
    p4x, p4y = p1x, p3y

    # 投影后顶点坐标
    rep1x, rep1y = ct.TransformPoint(p1x, p1y)[0:2]
    rep2x, rep2y = ct.TransformPoint(p2x, p2y)[0:2]
    rep3x, rep3y = ct.TransformPoint(p3x, p3y)[0:2]
    rep4x, rep4y = ct.TransformPoint(p4x, p4y)[0:2]

    minX = min(rep1x, rep4x)
    maxX = max(rep2x, rep3x)
    minY = min(rep3y, rep4y)
    maxY = max(rep1y, rep2y)

    # 49度带的对角坐标
    ulx = int(minX / pixel_spacing) * pixel_spacing
    uly = int(np.ceil((maxY) / pixel_spacing)) * pixel_spacing
    lrx = int(np.ceil((maxX) / pixel_spacing)) * pixel_spacing
    lry = int(minY / pixel_spacing) * pixel_spacing
    Width = int((lrx - ulx) / pixel_spacing)
    Heigth = int((uly - lry) / pixel_spacing)

    ulx = int(ulx)
    uly = int(uly)

    for row in range(block_num):
        for column in range(block_num):
            p1x, p1y = geo_t[0] + column*block_step*pixel_spacing, geo_t[3] - row*block_step*pixel_spacing
            block.append([SrcEPSG,TargetEPSG,pixel_spacing,p1x,p1y,block_step,block_step])

    with Pool(5) as p:
        ImgBlock = p.map(BckParameterGenerator,block)
    # print(len(ImgBlock))
    Fill_value = 20000
    ParImgX = np.zeros(shape=(y_size, x_size), dtype=np.int32)
    ParImgY = np.zeros(shape=(y_size, x_size), dtype=np.int32)
    ParImgXGp = np.zeros(shape=(y_size, x_size), dtype=np.int32)
    ParImgYGp = np.zeros(shape=(y_size, x_size), dtype=np.int32)
    if pixel_spacing == 10:
        for row in range(6):
            for column in range(6):
                ParImgX[row*block_step:(row+1)*block_step,column*block_step:(column+1)*block_step] = ImgBlock[row*6+column][0]
        ParImgX[ParImgX !=Fill_value] = ((ParImgX - ulx -pixel_spacing/2)/pixel_spacing)[ParImgX !=Fill_value]
        path = OutPutDir+'\\'+'{}_TO{}_R{}_ParaX_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,10,ulx,uly,Width,Heigth)
        write_Img(ParImgX,path,proj,geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del  ParImgX

        for row in range(6):
            for column in range(6):
                ParImgY[row*block_step:(row+1)*block_step,column*block_step:(column+1)*block_step] = ImgBlock[row*6+column][1]
        ParImgY[ParImgY != Fill_value] = ((uly  - ParImgY -pixel_spacing / 2) / pixel_spacing)[ParImgY != Fill_value]
        path = OutPutDir+'\\'+r'{}_TO{}_R{}_ParaY_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,10,ulx,uly,Width,Heigth)
        write_Img(ParImgY,path,proj,geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgY

        for row in range(6):
            for column in range(6):
                ParImgXGp[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                ImgBlock[row * 6 + column][2]
        ParImgXGp[ParImgXGp != Fill_value] = (ParImgXGp[ParImgXGp != Fill_value] - ulx - pixel_spacing / 2) / pixel_spacing
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaXGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,10,ulx,uly,Width,Heigth)
        write_Img(ParImgXGp, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgXGp

        for row in range(6):
            for column in range(6):
                ParImgYGp[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                ImgBlock[row * 6 + column][3]
        ParImgYGp[ParImgYGp != Fill_value] = ((uly - ParImgYGp- pixel_spacing / 2) / pixel_spacing)[ParImgYGp != Fill_value]
        path = OutPutDir+'\\'+r'{}_TO{}_R{}_ParaYGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,10,ulx,uly,Width,Heigth)
        write_Img(ParImgYGp, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgYGp


    # 20m
    if pixel_spacing == 20:
        for row in range(3):
            for column in range(3):
                ParImgX[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                ImgBlock[row * 3 + column][0]
        ParImgX[ParImgX != Fill_value] = ((ParImgX - ulx - pixel_spacing / 2) / pixel_spacing)[ParImgX != Fill_value]
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaX_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        write_Img(ParImgX, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgX

        for row in range(3):
            for column in range(3):
                ParImgY[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                ImgBlock[row * 3 + column][1]
        ParImgY[ParImgY != Fill_value] = ((uly - ParImgY - pixel_spacing / 2) / pixel_spacing)[ParImgY != Fill_value]
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaY_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        write_Img(ParImgY, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgY
        # vv = ParImgX == Fill_value
        # hh = ParImgY == Fill_value
        # print(np.sum(vv),np.sum(hh))

        for row in range(3):
            for column in range(3):
                ParImgXGp[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                    ImgBlock[row * 3 + column][2]
        ParImgXGp[ParImgXGp != Fill_value] = ((ParImgXGp - ulx - pixel_spacing / 2) / pixel_spacing)[ParImgXGp != Fill_value]
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaXGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        write_Img(ParImgXGp, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgXGp

        for row in range(3):
            for column in range(3):
                ParImgYGp[row * block_step:(row + 1) * block_step, column * block_step:(column + 1) * block_step] = \
                    ImgBlock[row * 3 + column][3]
        ParImgYGp[ParImgYGp != Fill_value] = ((uly - ParImgYGp - pixel_spacing / 2) / pixel_spacing)[ParImgYGp != Fill_value]
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaYGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        write_Img(ParImgYGp, path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgYGp
    if pixel_spacing == 60:
        path = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaX_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        path1 = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaY_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        path2 = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaXGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        path3 = OutPutDir+'\\'+ r'{}_TO{}_R{}_ParaYGap_E{}_N{}_W{}_H{}.tif'.format(TileName,ToTileName,pixel_spacing,ulx,uly,Width,Heigth)
        ParImgX[ParImgX != Fill_value] = ((ParImgX - ulx - pixel_spacing / 2) / pixel_spacing)[ParImgX != Fill_value]
        ParImgY[ParImgY != Fill_value] = ((uly - ParImgY - pixel_spacing / 2) / pixel_spacing)[ParImgY != Fill_value]
        ParImgXGp[ParImgXGp != Fill_value] = ((ParImgXGp - ulx - pixel_spacing / 2) / pixel_spacing)[ParImgXGp !=Fill_value]
        ParImgYGp[ParImgYGp != Fill_value] = ((uly - ParImgYGp - pixel_spacing / 2) / pixel_spacing)[ParImgYGp != Fill_value]
        write_Img(ImgBlock[0][0], path, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        write_Img(ImgBlock[0][1], path1, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        write_Img(ImgBlock[0][2], path2, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        write_Img(ImgBlock[0][3], path3, proj, geo_t, x_size, y_size, im_bands=1, dtype=gdal.GDT_UInt16)
        del ParImgX
        del ParImgY
        del ParImgXGp
        del ParImgYGp
        end =time.time()
        print("I am done,cost time for {} s".format(end-st))




