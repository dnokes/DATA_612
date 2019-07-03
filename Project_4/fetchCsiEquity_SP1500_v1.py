# -*- coding: utf-8 -*-
"""
Created on Tue Dec 26 22:31:32 2017

@author: Derek G Nokes (dgn2)
"""



import mysqlDatabaseToolbox
import win32com.client
import os
import datetime
import dateutil
import pandas
import math
import numpy
from scipy import stats
from timeit import default_timer as timer

## graphics
#import matplotlib.pyplot as plt
#import matplotlib.patches as mpatches
#dpi=300
#plt.rc("savefig", dpi=dpi)
#plt.rcParams['figure.dpi']= dpi
#import seaborn

# initiate CSI UA data update
def updateCsiUa(): 
    ua=win32com.client.Dispatch("UA.API2")
    errno=ua.UpdateDatabase()
    return errno

# close CSI UA application
def killua():
    ua=win32com.client.Dispatch("UA.API2")
    errno=None
    # set to 0 to close
    # set to 1 (default) to keep open
    ua.HoldUAOpenOnClose=0 
    return errno

# map CSI ticker to CSI number
def csiTicker2Number(csiTicker):
    ua=win32com.client.Dispatch("UA.API2")
    ua.MarketSymbol = csiTicker
    ua.IsStock = 1
    csiNumber=ua.FindMarketNumber()

    return csiNumber

## compute price momentum
def price2momentum(y):
    x=numpy.arange(0,len(y))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x,
        numpy.log(y))
    # adjust the momentum for smoothness and annualize
    momentum=(((1+slope)**252)-1)*(r_value**2)
    return momentum

# apply price gap filter
def priceGapFilter(y):
    # set gap filter
    threshold=0.15
    # find gap flag
    gapFlag=numpy.max(numpy.abs(numpy.diff(numpy.log(y))))>=threshold

    return gapFlag

# convert CSI date to datetime
def csiDate2DateTime(d):
    t=str(d)
    YYYY=int(t[0:4])
    MM=int(t[4:6])
    DD=int(t[6:8])
    #dateTime=datetime.datetime(YYYY,MM,DD)
    dateTime=datetime.date(YYYY,MM,DD)
    return dateTime

# create directory if it does not exist
def ensureDirectory(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)
    return f

# get dividend-adjusted spot equity for CSI ticker
def getDividendAdjustedSpotEquity(csiTicker,csiNumber,startDate=-1,endDate=-1,atrLookback=20):
    # convert ticker to CSI number
    #csiNumber=csiTicker2Number(csiTicker)  
    # connect to UA API
    ua=win32com.client.Dispatch("UA.API2")
    # turn on decimal
    ua.ShowDecimalPoint = 1
    # turn on holiday inclusion
    ua.IncludeHolidays = 1
    # turn off detrend
    ua.detrendMethod = 0
    # turn off fill in cash price
    ua.FillInCashPrice = 0
    # turn on out of range adjustment
    ua.CloseOutOfRangeAdjustmentMethod = 1
    # apply stock split adjustment
    ua.ApplyStockSplitAdjustments = 0
    # apply stock dividend adjustment
    ua.ApplyStockDividendAdjustments = 1
    # turn off proportional price adjustments
    ua.PropStockAdjustments=1
    # turn off proportional volume adjustments
    ua.PropStockVolumeAdjustments=0
    # fetch the data
    numberOfDates=ua.RetrieveStock(csiNumber,startDate,endDate)
    # extract the data to an array 
    data=ua.CopyRetrievedDataToArray(0)
    # set the column names
    columnNames=['date','dayOfWeek','deliv','open','high','low','close',
        'unadjClose','cash','volume','OI','totalVolume','totalOI','cash']
    # create the data frame
    equityData=pandas.DataFrame(zip(*list(data[1:])),columns = columnNames)
    # convert the int YYYYMMDD date to a datetime
    equityData['date']=equityData['date'].apply(csiDate2DateTime)
    # remove unnecessary columns 
    equityData=equityData.drop(['deliv','unadjClose','cash','OI',
        'totalVolume','totalOI','cash'], axis=1)
    # find good business days
    goodBusinessDayIndex=equityData['dayOfWeek'] != 8
    # extract data for good business days
    equityDataATR=equityData[goodBusinessDayIndex]
    # lag the close price
    previousClosePrice=equityDataATR['close'].shift(1)
    # determine the range
    a=equityDataATR['high']-equityDataATR['low']
    # determine distance between previous close and the high
    b=abs(equityDataATR['high']-previousClosePrice)
    # determine the distance between the previous close and the low
    c=abs(previousClosePrice-equityDataATR['low'])
    # concatenate the range components
    rangeComponents=pandas.concat([a,b,c],axis=1)
    # compute true range
    trueRange=rangeComponents.max(axis=1,skipna=False)
    # compute the average true range
    atr=trueRange.ewm(span=atrLookback,min_periods=atrLookback,adjust=True,
        ignore_na=True).mean()  
    # reindex the true range to include holidays 
    trueRange.reindex(equityData.index,method='ffill')
    # reindex the ATR to include holidays 
    atr.reindex(equityData.index,method='ffill')
    # add the true range to the data frame
    equityData['trueRange']=trueRange
    # add the average true range to the data frame
    equityData['atr']=atr
    # add CSI number
    equityData['csiNumber']=csiNumber
    # add CSI ticker
    equityData['instrumentTicker']=csiTicker

    return equityData

# get split-adjusted spot equity for CSI ticker
def getSplitAdjustedSpotEquity(csiTicker,csiNumber,startDate=-1,endDate=-1,atrLookback=20):
    # convert ticker to CSI number
    #csiNumber=csiTicker2Number(csiTicker)  
    # connect to UA API
    ua=win32com.client.Dispatch("UA.API2")
    # turn on decimal
    ua.ShowDecimalPoint = 1
    # turn on holiday inclusion
    ua.IncludeHolidays = 1
    # turn off detrend
    ua.detrendMethod = 0
    # turn off fill in cash price
    ua.FillInCashPrice = 0
    # turn on out of range adjustment
    ua.CloseOutOfRangeAdjustmentMethod = 1
    # apply stock split adjustment
    ua.ApplyStockSplitAdjustments = 1
    # apply stock dividend adjustment
    ua.ApplyStockDividendAdjustments = 0
    # turn off proportional price adjustments
    ua.PropStockAdjustments=1
    # turn off proportional volume adjustments
    ua.PropStockVolumeAdjustments=0
    # fetch the data
    numberOfDates=ua.RetrieveStock(csiNumber,startDate,endDate)
    # extract the data to an array 
    data=ua.CopyRetrievedDataToArray(0)
    # set the column names
    columnNames=['date','dayOfWeek','deliv','open','high','low','close',
        'unadjClose','cash','volume','OI','totalVolume','totalOI','cash']
    # create the data frame
    equityData=pandas.DataFrame(zip(*list(data[1:])),columns = columnNames)
    # convert the int YYYYMMDD date to a datetime
    equityData['date']=equityData['date'].apply(csiDate2DateTime)
    # remove unnecessary columns 
    equityData=equityData.drop(['deliv','unadjClose','cash','OI',
        'totalVolume','totalOI','cash'], axis=1)
    # find good business days
    goodBusinessDayIndex=equityData['dayOfWeek'] != 8
    # extract data for good business days
    equityDataATR=equityData[goodBusinessDayIndex]
    # lag the close price
    previousClosePrice=equityDataATR['close'].shift(1)
    # determine the range
    a=equityDataATR['high']-equityDataATR['low']
    # determine distance between previous close and the high
    b=abs(equityDataATR['high']-previousClosePrice)
    # determine the distance between the previous close and the low
    c=abs(previousClosePrice-equityDataATR['low'])
    # concatenate the range components
    rangeComponents=pandas.concat([a,b,c],axis=1)
    # compute true range
    trueRange=rangeComponents.max(axis=1,skipna=False)
    # compute the average true range
    atr=trueRange.ewm(span=atrLookback,min_periods=atrLookback,adjust=True,
        ignore_na=True).mean()     
    # reindex the true range to include holidays 
    trueRange.reindex(equityData.index,method='ffill')
    # reindex the ATR to include holidays 
    atr.reindex(equityData.index,method='ffill')
    # add the true range to the data frame
    equityData['trueRange']=trueRange
    # add the average true range to the data frame
    equityData['atr']=atr
    # add CSI number
    equityData['csiNumber']=csiNumber
    # add CSI ticker
    equityData['instrumentTicker']=csiTicker

    return equityData

# get split- and dividend- adjusted spot equity for CSI ticker
def getSplitAndDividendAdjustedSpotEquity(csiTicker,csiNumber,startDate=-1,endDate=-1,atrLookback=20):
    # convert ticker to CSI number
    #csiNumber=csiTicker2Number(csiTicker)  
    # connect to UA API
    ua=win32com.client.Dispatch("UA.API2")
    # turn on decimal    
    ua.ShowDecimalPoint = 1
    # turn on holiday inclusion
    ua.IncludeHolidays = 1
    # turn off detrend
    ua.detrendMethod = 0
    # turn off fill in cash price
    ua.FillInCashPrice = 0
    # apply close out of range adjustment
    ua.CloseOutOfRangeAdjustmentMethod = 1
    # apply stock split adjustment
    ua.ApplyStockSplitAdjustments = 1
    # apply stock dividend adjustment
    ua.ApplyStockDividendAdjustments = 1
    # turn off proportional price adjustments
    ua.PropStockAdjustments=1
    # turn off proportional volume adjustments
    ua.PropStockVolumeAdjustments=0
    # fetch the data
    numberOfDates=ua.RetrieveStock(csiNumber,startDate,endDate)
    # extract the data to an array
    data=ua.CopyRetrievedDataToArray(0)
    # set the column names
    columnNames=['date','dayOfWeek','deliv','open','high','low','close',
        'unadjClose','cash','volume','OI','totalVolume','totalOI','cash']
    # create the data frame
    equityData=pandas.DataFrame(zip(*list(data[1:])),columns = columnNames)
    # remove unnecessary columns 
    equityData=equityData.drop(['deliv','unadjClose','cash','OI',
        'totalVolume','totalOI','cash'], axis=1)
    # convert the int YYYYMMDD date to a datetime
    equityData['date']=equityData['date'].apply(csiDate2DateTime)    
    # find good business days
    goodBusinessDayIndex=equityData['dayOfWeek'] != 8
    # extract data for good business days
    equityDataATR=equityData[goodBusinessDayIndex]
    # lag the close price
    previousClosePrice=equityDataATR['close'].shift(1)
    # determine the range
    a=equityDataATR['high']-equityDataATR['low']
    # determine distance between previous close and the high
    b=abs(equityDataATR['high']-previousClosePrice)
    # determine the distance between the previous close and the low
    c=abs(previousClosePrice-equityDataATR['low'])
    # concatenate the range components
    rangeComponents=pandas.concat([a,b,c],axis=1)
    # compute true range
    trueRange=rangeComponents.max(axis=1,skipna=False)
    # compute the average true range
    atr=trueRange.ewm(span=atrLookback,min_periods=atrLookback,adjust=True,
        ignore_na=True).mean()  
    # reindex the true range to include holidays 
    trueRange.reindex(equityData.index,method='ffill')
    # reindex the ATR to include holidays 
    atr.reindex(equityData.index,method='ffill')
    # add the true range to the data frame
    equityData['trueRange']=trueRange
    # add the average true range to the data frame
    equityData['atr']=atr
    # add CSI number
    equityData['csiNumber']=csiNumber
    # add CSI ticker
    equityData['instrumentTicker']=csiTicker
 
    return equityData

# get non-adjusted spot equity for CSI ticker
def getNonAdjustedSpotEquity(csiTicker,csiNumber,startDate=-1,endDate=-1):
    # map ticker to CSI number
    #csiNumber=csiTicker2Number(csiTicker)  
    # connect to UA API
    ua=win32com.client.Dispatch("UA.API2")
    # turn on decimal
    ua.ShowDecimalPoint = 1
    # turn on holiday inclusion
    ua.IncludeHolidays = 1
    # turn off detrend
    ua.detrendMethod = 0
    # turn off fill in cash price
    ua.FillInCashPrice = 0
    # turn on out of range adjustment
    ua.CloseOutOfRangeAdjustmentMethod = 1
    # turn on split adjustment
    ua.ApplyStockSplitAdjustments = 0
    # turn on dividend adjustment
    ua.ApplyStockDividendAdjustments = 0
    # turn off proportional price adjustments
    ua.PropStockAdjustments=0
    # turn off proportional volume adjustments
    ua.PropStockVolumeAdjustments=0
    # fetch the data
    numberOfDates=ua.RetrieveStock(csiNumber,startDate,endDate)
    # extract the data to an array
    data=ua.CopyRetrievedDataToArray(0)
    # set the column names
    columnNames=['date','dayOfWeek','deliv','open','high','low','close',
        'unadjClose','cash','volume','OI','totalVolume','totalOI','cash']
    # create the data frame
    equityData=pandas.DataFrame(zip(*list(data[1:])),columns = columnNames)
    # remove unnecessary columns 
    equityData=equityData.drop(['deliv','unadjClose','cash','OI',
        'totalVolume','totalOI','cash'], axis=1)
    # convert the int YYYYMMDD date to a datetime
    equityData['date']=equityData['date'].apply(csiDate2DateTime)
    # add CSI number
    equityData['csiNumber']=csiNumber
    # add CSI ticker
    equityData['instrumentTicker']=csiTicker
            
    return equityData

# get corporate actions data for CSI ticker
def getCorporateActions(csiTicker,csiNumber,startDate=-1,endDate=-1):
    
    try:
        startDate=startDate.strftime('%Y%m%d')
        endDate=endDate.strftime('%Y%m%d')
    except:
        pass    
    
    # convert ticker to CSI number
    #csiNumber=csiTicker2Number(csiTicker)  
    # connect to UA API
    ua=win32com.client.Dispatch("UA.API2")
    # fetch the data
    corporateActionData=ua.RetrieveDividendsSplitsAndCapitalGains(csiNumber,1,
        startDate,endDate)
            
    try:
        # create the data frame
        dividendData=pandas.DataFrame(zip(*list(corporateActionData[3:5])),
            index=list(corporateActionData[3]),columns=['dividendDate',
            'dividend'])
        # convert the int YYYYMMDD date to a datetime
        dividendData['dividendDate']=dividendData['dividendDate'].apply(csiDate2DateTime)
        # add CSI number
        dividendData['csiNumber']=csiNumber
        # add CSI ticker
        dividendData['instrumentTicker']=csiTicker        
        
    except:
        dividendData=None
    try:
        # create the data frame
        capitalGainsData=pandas.DataFrame(zip(*list(corporateActionData[5:7])),
            index=list(corporateActionData[5]),columns=['corporateGainsDate',
            'corporateGain'])
        # convert the int YYYYMMDD date to a datetime
        capitalGainsData['corporateGainsDate']=capitalGainsData['corporateGainsDate'].apply(csiDate2DateTime)
    except:
        capitalGainsData=None
    
    try:
        # create the data frame
        splitData=pandas.DataFrame(zip(*list(corporateActionData[7:10])),
            index=list(corporateActionData[7]),columns=['splitDate','splitTo',
            'splitFrom'])
        # convert the int YYYYMMDD date to a datetime
        splitData['splitDate']=splitData['splitDate'].apply(csiDate2DateTime)
        # add CSI number
        splitData['csiNumber']=csiNumber
        # add CSI ticker
        splitData['instrumentTicker']=csiTicker          
    except:
        splitData=None
                    
    return dividendData,capitalGainsData,splitData

# get equity spot and corporate actions for CSI ticker
def getEquitySpotAndCorporateActions(csiTicker,csiNumber,startDate=-1,
    endDate=-1,atrLookback=20):
    
    try:
        startDate=startDate.strftime('%Y%m%d')
        endDate=endDate.strftime('%Y%m%d')
    except:
        pass
    
    # get the non-adjusted spot equity for CSI number
    nonAdjustedData=getNonAdjustedSpotEquity(csiTicker,csiNumber,startDate,
        endDate)
    # assign the column names
    columnNames=list(nonAdjustedData)
    columnNames[0]='asOfDate'
    columnNames[1]='dayOfWeek'
    columnNames[2]='openPriceNonAdjusted'
    columnNames[3]='highPriceNonAdjusted'
    columnNames[4]='lowPriceNonAdjusted'
    columnNames[5]='closePriceNonAdjusted'
    columnNames[6]='volumeNonAdjusted'
    columnNames[7]='csiNumber'
    columnNames[8]='instrumentTicker'

    # assign the column names
    nonAdjustedData.columns=columnNames           
    # get the split adjusted spot equity data for CSI number
    splitAdjustedData=getSplitAdjustedSpotEquity(csiTicker,csiNumber,startDate,
        endDate,atrLookback)   
    # assign the column names
    columnNames=list(splitAdjustedData)
    columnNames[0]='asOfDate_S'
    columnNames[1]='dayOfWeek_S'
    columnNames[2]='openPriceAdjusted_S'
    columnNames[3]='highPriceAdjusted_S'
    columnNames[4]='lowPriceAdjusted_S'
    columnNames[5]='closePriceAdjusted_S'
    columnNames[6]='volumeAdjusted_S'    
    columnNames[7]='trueRange_S'
    columnNames[8]='atr_S'
    columnNames[9]='csiNumber_S'
    columnNames[10]='instrumentTicker_S'
                
    # assign the column names
    splitAdjustedData.columns=columnNames
    # merge the split-adjusted and non-adjusted data
    data=pandas.merge(nonAdjustedData,splitAdjustedData,left_on='asOfDate',
        right_on='asOfDate_S',how='left')
    # delete the split-adjusted data object
    del splitAdjustedData
    # delete the split and dividend -adjusted data object
    del nonAdjustedData
    # get split and dividend adjusted spot equity for CSI ticker
    splitAndDividendAdjustedData=getSplitAndDividendAdjustedSpotEquity(
        csiTicker,csiNumber,startDate,endDate,atrLookback)
    # assign the column names
    columnNames=list(splitAndDividendAdjustedData)
    columnNames[0]='asOfDate_S_D'
    columnNames[1]='dayOfWeek_S_D'
    columnNames[2]='openPriceAdjusted_S_D'
    columnNames[3]='highPriceAdjusted_S_D'
    columnNames[4]='lowPriceAdjusted_S_D'
    columnNames[5]='closePriceAdjusted_S_D'
    columnNames[6]='volumeAdjusted_S_D'    
    columnNames[7]='trueRange_S_D'
    columnNames[8]='atr_S_D'
    columnNames[9]='csiNumber_S_D'
    columnNames[10]='instrumentTicker_S_D'
    
    # assign the column names
    splitAndDividendAdjustedData.columns=columnNames
    # merge the split- and dividend- adjusted and non-adjusted data
    data=pandas.merge(data,splitAndDividendAdjustedData,left_on='asOfDate',
        right_on='asOfDate_S_D',how='left')

    # get the corporate actions data
    try:
        # fetch the corporate action data
        dividendData,capitalGainsData,splitData=getCorporateActions(
            csiTicker,csiNumber,startDate,endDate)
        # if dividend data exists       
        if (len(dividendData)>0):
            # drop the CSI number and instrument ticker
            dividendData=dividendData.drop(['csiNumber','instrumentTicker'], 
                axis=1)
            # add the dividend data
            data=pandas.merge(data,dividendData,left_on='asOfDate',
                right_on='dividendDate',how='left')
            # create the columns not required
            data=data.drop(['dividendDate'], axis=1)
        # if dividend data does not exist
        else:
            data['dividend']=numpy.nan
        # if split data exists     
        if (len(splitData)>0):
            # drop the CSI number and instrument ticker
            splitData=splitData.drop(['csiNumber','instrumentTicker'], 
                axis=1)            
            # add the split data
            data=pandas.merge(data,splitData,left_on='asOfDate',
                right_on='splitDate',how='left')
            # create the columns not required
            data=data.drop(['splitDate'], axis=1)
        # if split data does not exist 
        else:
            data['splitTo']=numpy.nan
            data['splitFrom']=numpy.nan
            
    except:
        pass
    # create the columns not required
    data=data.drop(['asOfDate_S','dayOfWeek_S','asOfDate_S_D','dayOfWeek_S_D',
        'csiNumber_S','instrumentTicker_S','csiNumber_S_D','instrumentTicker_S_D'],
        axis=1)
    # add date and instrument ticker index
    data.set_index(keys=['asOfDate','instrumentTicker'],inplace=True)
    # find good business day index
    goodBusinessDayIndex=data['dayOfWeek'] != 8
    
    # return data for good business days
    return data.loc[goodBusinessDayIndex]

# update h5 equity data files using CSI UA
def updateDataCSI(instrumentList,startDate,endDate,baseDirectory,universeName,floatFormat):

    # define strategy parameters
    atrLookback=20
    momentumLookback=90
    gapLookback=90
    emaLookbackS=120
    emaLookbackL=180
    
    # determine current datetime
    runDateTime=datetime.datetime.now()    
    # define output directory for universe
    outputDirectory=baseDirectory+'/'+universeName+'/raw/'
    # define output folders
    a=outputDirectory+'/non_adjusted/'
    b=outputDirectory+'/corporate_actions/'
    c=outputDirectory+'/split_adjusted/'
    d=outputDirectory+'/dividend_adjusted/'
    e=outputDirectory+'/split_and_dividend_adjusted/'
    f=outputDirectory+'/dividend/'
    g=outputDirectory+'/split/'
    # create output folders for each data type
    ensureDirectory(a)
    ensureDirectory(b)
    ensureDirectory(c)
    ensureDirectory(d)
    ensureDirectory(e)
    ensureDirectory(f)
    ensureDirectory(g)
    # define error log directory
    errorDirectory=outputDirectory
    # define error log file name
    errorFileName='error_csi_'+runDateTime.strftime('%Y%m%d')
    # open error log file handle
    errorFileHandle = open(errorDirectory+errorFileName,'w')
    # add error log header
    errorFileHandle.write('\n')
    
    # start timer (prices)
    ts_fetchPrices = timer()

    dataDictionary=dict()
    error=dict()    
    
    # iterate over each instrument in the index
    for instrument_index, instrument in instrumentList.iterrows():
        #
        csiNumber=instrument['csi_number']
        csiTicker=instrument['instrument_ticker']
        instrumentName=instrument['instrument_name']
        sector=instrument['sector']
        sedol=instrument['sedol']
        isin=instrument['isin']
        indexName=instrument['index_name']
        holdingsAsOfDate=instrument['holdings_as_of_date']
        
        print(str(csiNumber)+"|"+csiTicker+"|"+instrumentName+"|"+sector+"|"+indexName)      
        #
        try:
            # get non-adjusted data
            nonAdjusted=getNonAdjustedSpotEquity(csiTicker,csiNumber,startDate,
                endDate)
            # write non-adjusted data
            nonAdjusted.to_csv(a + csiTicker,sep='|',mode='w',header=True,
                float_format=floatFormat,na_rep='\N',index=False)
            # add to h5 file
            
        #
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|nonAdjusted\n"
            errorFileHandle.write(errorMessage)
        
        #
        try:
            # get dividend-adjusted data
            dividendAdjusted=getDividendAdjustedSpotEquity(csiTicker,csiNumber,
                startDate,endDate,atrLookback)
            # write dividend-adjusted data
            dividendAdjusted.to_csv(d + csiTicker,sep='|',mode='w',header=True,
                float_format=floatFormat,na_rep='\N',index=False)
            # add to h5 file
            
        #
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|dividendAdjusted\n"
            errorFileHandle.write(errorMessage)
    
        try:
            # get split-adjusted data 
            splitAdjusted=getSplitAdjustedSpotEquity(csiTicker,csiNumber,startDate,
                endDate,atrLookback)
            # write split-adjusted data
            splitAdjusted.to_csv(c + csiTicker,sep='|',mode='w',header=True,
                float_format=floatFormat,na_rep='\N',index=False)
            # add to h5 file
            
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|splitAdjusted\n"
            errorFileHandle.write(errorMessage)
    
        try:
            # get split- and dividend- adjusted data
            splitAndDividendAdjusted=getSplitAndDividendAdjustedSpotEquity(
                csiTicker,csiNumber,startDate,endDate,atrLookback)
            # write split- and dividend- adjusted data
            splitAndDividendAdjusted.to_csv(e + csiTicker,sep='|',mode='w',header=True,
                float_format=floatFormat,na_rep='\N',index=False)
            # add to h5 file
            
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|splitAndDividendAdjusted\n"
            errorFileHandle.write(errorMessage)

        try:
            # get equity spot and corporate actions data
            data=getEquitySpotAndCorporateActions(csiTicker,csiNumber,startDate,
                endDate,atrLookback)
            # add momentum
            data['momentum_'+str(momentumLookback)+'d']=data['closePriceAdjusted_S_D'].rolling(
                center=False,window=momentumLookback).apply(func=price2momentum)
            # add gap flag
            data['gapFlag_'+str(gapLookback)+'d']=data['closePriceAdjusted_S_D'].rolling(
                center=False,window=gapLookback).apply(func=priceGapFilter)    
            # compute EMA prices
            data['emaPrice_'+str(emaLookbackS)+'d']=data['closePriceAdjusted_S_D'].ewm(
                span=emaLookbackS,min_periods=emaLookbackS,ignore_na=True).mean()
            data['emaPrice_'+str(emaLookbackL)+'d']=data['closePriceAdjusted_S_D'].ewm(
                span=emaLookbackL,min_periods=emaLookbackL,ignore_na=True).mean()            
            
            # write corporate actions data
            data.to_csv(b + csiTicker,sep='|',mode='w',header=True,
                float_format=floatFormat,na_rep='\N',index=True,
                index_label=['asOfDate','instrumentTicker'])
            # add price dataframe to data dictionary 
            dataDictionary[csiTicker]=data            
            # add to h5 file
            
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|all\n"
            errorFileHandle.write(errorMessage)

        # corporate actions
        try:
            # get corporate actions data
            dividendData,capitalGainsData,splitData=getCorporateActions(
                csiTicker,csiNumber,startDate,endDate)
            # write dividend data
            if (len(dividendData)>0):
                # write the dividend data
                dividendData.to_csv(f + csiTicker,sep='|',mode='w',header=True,
                    na_rep='\N',index=False)
                # add to h5 file
                
            # write split data
            if (len(splitData)>0):
                # write the split data
                splitData.to_csv(g+ csiTicker,sep='|',mode='w',header=True,
                    na_rep='\N',index=False)
                # add to h5 file
                
        #
        except:
            errorMessage=str(instrument[0])+"|"+str(instrument[1])+"|"+str(csiTicker)+"|corporateActions\n"
            errorFileHandle.write(errorMessage)

    # close error tracking output file handle
    errorFileHandle.close()

    # end timer (prices)
    te_fetchPrices = timer()

    # compute time elasped
    timeElasped_fetchPrices=te_fetchPrices-ts_fetchPrices

    # display time elasped
    print('Time Elasped: '+str(timeElasped_fetchPrices))    
    
    # create the data panel
    #groupData=pandas.Panel.from_dict(dataDictionary,orient='minor')
    
    # create multi-index dataframe

    # concatenate data frames for all tickers
    groupData=pandas.concat(dataDictionary)
    # reset index
    groupData.reset_index(inplace=True)
    # drop 'level_0' column
    groupData.drop(['level_0'], axis=1,inplace=True)
    # set index to as-of date and instrument ticker
    groupData.set_index(['asOfDate','instrumentTicker'],inplace=True)    

    return groupData,dataDictionary

# add write group data to H5
def groupData2H5(groupData,baseDirectory,universeName):
    # define h5 output file name   
    outputFileNameH5=universeName+'_csi.h5'
    # create HDF5 data store
    data_store = pandas.HDFStore(baseDirectory+outputFileNameH5)
    # iterate over each column
    for columnName in groupData.columns.values:
        if ((columnName != 'csiNumber') | (columnName != 'dayOfWeek')):
            # store unstacked data frame for field in HDF5 data store
            data_store[columnName] = groupData[columnName].unstack()

    # store instrument master
    #data_store['instrumentMaster'] = instrumentMaster  
    
    # close the HDF5 data store
    data_store.close()
    # return output h5 file name
    return outputFileNameH5


def save2h5(baseDirectory,universeName,instrumentList,groupData):
    # extract prices
    prices=groupData['closePriceAdjusted_S_D'].unstack()
    # extract true ranges
    trueRanges=groupData['trueRange_S_D'].unstack()
    # extract ATRs
    atrs=groupData['atr_S_D'].unstack()
    # set HDF5 output file directory
    outputDirectoryH5=baseDirectory+"/h5/"
    # create directory if it does not exist
    ensureDirectory(outputDirectoryH5)
    outputFileNameH5=universeName+'_csi.h5'
    # create HDF5 data store
    data_store = pandas.HDFStore(outputDirectoryH5+outputFileNameH5)
    # store 'prices' data frame in HDF5 data store
    data_store['price'] = prices
    # store 'true ranges' data frame in HDF5 data store
    data_store['trueRange'] = trueRanges
    # store 'ATR' data frame in HDF5 data store
    data_store['atr'] = atrs
    # store instrument master
    data_store['instrumentMaster'] = instrumentList
    # close the HDF5 data store
    data_store.close()      
    
    return outputDirectoryH5,outputFileNameH5

## database parameter
#dbHost='localhost'
#dbPort=3306
#dbUser='root'
#dbPassword='TGDNrx78'
#databaseName='global_monitoring'
#
## connect to the 'global_monitoring' MySQL database 
#dbHandle=mysqlDatabaseToolbox.dbConnect(dbHost,dbPort,dbUser,dbPassword,
#    databaseName)

#query="SELECT instrumentTicker,instrumentName,sectorGICS,subIndustryGICS FROM sp500_constituents_by_sector;"
#
## fetch S&P500 constituents
#instrumentList=pandas.io.sql.read_sql(query,con=dbHandle)

## disconnect from MySQL
#mysqlDatabaseToolbox.dbDisconnect(dbHandle)


inputDirectory='F:/Dropbox/marketData/global_monitoring/csi/equity/instrument_master/'
inputFileName='csi-instrument-master_20190531'

instrumentList=pandas.read_csv(inputDirectory+inputFileName,sep="|")

#updateCsiUa()

# define output directory name
baseDirectory='F:/marketData/global_monitoring/csi/data/equity/'
universeName='single_stock'
# define parameters to fetch CSI UA data
startDate=-1
endDate=-1
floatFormat='%g'
# ensure output directory exists
ensureDirectory(baseDirectory)
# update CSI data
groupData,dataDictionary=updateDataCSI(instrumentList,startDate,endDate,baseDirectory,
    universeName,floatFormat)
# write to h5
outputDirectoryH5,outputFileNameH5=save2h5(baseDirectory,universeName,instrumentList,groupData)