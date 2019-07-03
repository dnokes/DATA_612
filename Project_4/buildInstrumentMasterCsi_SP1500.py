# -*- coding: utf-8 -*-
"""
Created on Mon Jul 01 08:43:32 2019

@author: Derek
"""
import win32com.client
import datetime
import pandas
import MySQLdb
import mysqlDatabaseToolbox
from timeit import default_timer as timer
import os
# extract equity data

def killua():
    ua=win32com.client.Dispatch("UA.API2")
    errno=None
    ua.HoldUAOpenOnClose=0 # 1 (default) keeps it open
    return errno

def updateCsiUa(): 
    ua=win32com.client.Dispatch("UA.API2")
    errno=ua.UpdateDatabase()
    return errno

def csiTicker2Number(csiTicker):
    ua=win32com.client.Dispatch("UA.API2")
    ua.MarketSymbol = csiTicker
    ua.IsStock = 1
    csiNumber=ua.FindMarketNumber()

    return csiNumber  

#
holdingsAsOfDate=datetime.date(2019,5,31)
masterDirectory="F:/Dropbox/marketData/global_monitoring/csi/equity/instrument_master/"
masterFileName="csi-instrument-master_"+holdingsAsOfDate.strftime("%Y%m%d")
# data server database parameters
dbHost='localhost'
dbPort=3306
dbUser='root'
dbPassword='TGDNrx78'
databaseName='global_monitoring'

# connect to the 'global_monitoring' MySQL database 
dbHandle=mysqlDatabaseToolbox.dbConnect(dbHost,dbPort,dbUser,dbPassword,
    databaseName)

# update CSI
#updateCsiUa()
# fetch index constituents (SP500, SP400, SP600) 
instrumentUniverse=pandas.io.sql.read_sql("SELECT instrument_ticker,instrument_name,sector,sedol,isin,index_name,holdings_as_of_date FROM global_monitoring.ishares_holdings_sp1500 WHERE holdings_as_of_date='"+holdingsAsOfDate.strftime("%Y-%m-%d")+"';",con=dbHandle,coerce_float=True)

# start timer (prices)
ts_fetchPrices = timer()
#
masterFileHandle=open(masterDirectory+masterFileName,'w')
# add header
masterFileHandle.write("mapped_flag|csi_number|instrument_ticker|instrument_name|sector|sedol|isin|index_name|holdings_as_of_date\n")
# iterate over instrument universe
for instrument_index, instrument in instrumentUniverse.iterrows():
    # extract instrument details
    instrument_ticker=instrument['instrument_ticker']
    instrument_name=instrument['instrument_name']
    sector=instrument['sector']
    sedol=instrument['sedol']
    isin=instrument['isin']
    index_name=instrument['index_name']
    holdings_as_of_date=instrument['holdings_as_of_date'].strftime("%Y-%m-%d")
    # try to map instrument ticker to CSI number
    try:
        # convert ticker to CSI number
        csiNumber=csiTicker2Number(instrument_ticker)
        # 
        if csiNumber==-1:
            # record unmapped instrument details
            masterFileHandle.write("Unmapped|"+str(csiNumber)+"|"+instrument_ticker+"|"+instrument_name+"|"+sector+"|"+sedol+"|"+isin+"|"+index_name+"|"+holdings_as_of_date+"\n")
        else:
            # record mapped instrument details
            masterFileHandle.write("Mapped|"+str(csiNumber)+"|"+instrument_ticker+"|"+instrument_name+"|"+sector+"|"+sedol+"|"+isin+"|"+index_name+"|"+holdings_as_of_date+"\n")
    # if ticker does not map to CSI number record as unknown
    except:
        masterFileHandle.write("Unmapped|Unknown|"+instrument_ticker+"|"+instrument_name+"|"+sector+"|"+sedol+"|"+isin+"|"+index_name+"|"+holdings_as_of_date+"\n")

# close output file
masterFileHandle.close()

# end timer (prices)
te_fetchPrices = timer()

# compute time elasped
timeElasped_fetchPrices=te_fetchPrices-ts_fetchPrices

# display time elasped
print('Time Elasped: '+str(timeElasped_fetchPrices))
