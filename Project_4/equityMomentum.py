# -*- coding: utf-8 -*-
"""
Created on Mon Jul 01 01:32:48 2019

@author: Derek
"""

# import the packages required for the project
import MySQLdb
import matplotlib.pyplot as plt
import seaborn
from timeit import default_timer as timer
import datetime
import dateutil
import requests
import pandas
import os
import shutil
import math
import numpy
import pandas.io.sql as sql
from pandas.tseries.offsets import CustomBusinessDay,MonthBegin
import pandas_datareader.data as web

from scipy import stats

# create directory if it does not exist
def ensureDirectory(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)
    return f

def emaNPaths(pricePaths,lookback):
    # find T and nPaths
    T,nPaths=pricePaths.shape
    # create output array
    ema=numpy.zeros([int(T),int(nPaths)])
    # compute the smoothing constant
    a = 2.0 / ( lookback + 1.0 )
    # iterate over each price path
    for pathIndex in range(0,int(nPaths)):
        # iterate over each price path
        ema[0,pathIndex] = pricePaths[0,pathIndex]
        # iterate over each point in time and compute the EMA 
        for t in range(1,T):
            ema[t,pathIndex]=a * (pricePaths[t,pathIndex]-ema[t-1,
                pathIndex]) + ema[t-1,pathIndex]
    return ema
    
# classical momentum
def momentum(pricePaths,lookback):
    # find T and nPaths
    T,nPaths=pricePaths.shape
    # create output array
    momentumPaths=numpy.zeros([int(T),int(nPaths)])
    # iterate over each price path
    for pathIndex in range(0,int(nPaths)):
        # iterate over each point in time and compute the EMA 
        for t in range(1,int(T)):
            if t>=lookback:
                momentumPaths[t,pathIndex]=((1+((numpy.log(pricePaths[t,
                    pathIndex])-numpy.log(pricePaths[t-lookback,
                    pathIndex]))/lookback))**252)-1

    return momentumPaths

# regression-based momentum
def regressionBasedMomentum(pricePaths,lookback):
    # find T and nPaths
    T,nPaths=pricePaths.shape
    # create the x-axis (time)
    x=numpy.arange(0,lookback)
    # create output array
    momentumPaths=numpy.zeros([int(T),int(nPaths)])
    # iterate over each price path
    for pathIndex in range(0,int(nPaths)):
        # iterate over each point in time and compute the EMA 
        for t in range(1,int(T)):
            if t>=lookback:
                # run regression
                slope, intercept, r_value, p_value, std_err = stats.linregress(x,
                    numpy.log(pricePaths[int(t-lookback):t,pathIndex]))
                # adjust the momentum for smoothness and annualize
                momentumPaths[t,pathIndex]=(((1+slope)**252)-1)*(r_value**2)
                                                  
    return momentumPaths
    
def gapFilter(pricePaths,lookback,threshold):
    # determine the number of rows and paths
    nRows,nPaths=pricePaths.shape
    # create output array
    gap=numpy.zeros([int(nRows),int(nPaths)])
    # iterate of each path
    for pathIndex in range(0,int(nPaths)):
        for t in range(0,int(nRows)):
            if t>=lookback:
                # find the max return gap over the interval between (t-lookback) and t
                gap[t,pathIndex]=numpy.max(numpy.abs(numpy.diff(numpy.log(pricePaths[int(t-lookback):t,
                    pathIndex]))))>=threshold
        
    return gap

def momentumCrossoverWithStop(strategyInputs):
    # extract strategy inputs/parameters
    
    # price by instrument    
    pricePaths=strategyInputs['pricePaths']
    # true range
    trueRangePaths=strategyInputs['trueRangePaths']
    # lookback for average true range indicator (ATR)
    atrLookback=strategyInputs['atrLookback']
    # number of ATRs used in stop placement and position sizing    
    atrMultiplier=strategyInputs['atrMultiplier']
    # lookback for the 'fast' EMA    
    fastLookback=strategyInputs['fastLookback']
    # lookback for the 'slow' EMA
    slowLookback=strategyInputs['slowLookback']
    # lookback for the momentum indicator
    momentumLookback=strategyInputs['momentumLookback']
    # True=long-only, False=long/short    
    longOnly=strategyInputs['longOnly']
    # initial account size    
    accountSize=strategyInputs['accountSize']
    fPercent=strategyInputs['fPercent']
    # number of days between portfolio rebalance    
    rebalanceN=strategyInputs['rebalanceN']
    # number of positions allowed    
    nPositions=strategyInputs['nPositions']
    # pre-compute the average true range
    atr=emaNPaths(trueRangePaths,atrLookback)
    # pre-compute fast EMA 
    emaFast=emaNPaths(pricePaths,fastLookback)
    # pre-compute slow EMA
    emaSlow=emaNPaths(pricePaths,slowLookback)
    # find the longest lookback
    lookback=numpy.max([fastLookback,slowLookback,atrLookback,momentumLookback])
    # determine the number of rows (T) and paths (instruments)
    T,nPaths=pricePaths.shape
    
    # create the output arrays
    position=numpy.zeros([int(T),int(nPaths)])
    stopLevel=numpy.zeros([int(T),int(nPaths)])
    momentumPaths=numpy.zeros([int(T),int(nPaths)])
    # compute momentum
    momentumIndicator=regressionBasedMomentum(pricePaths,momentumLookback)
    
    stopLevel[:] = numpy.nan
    
    tradeSize=numpy.zeros([int(1),int(nPaths)])
    tradePrice=numpy.zeros([int(1),int(nPaths)])
    exitMarkToMarket=numpy.zeros([int(1),int(nPaths)])
    costOfExposure=numpy.zeros([int(1),int(nPaths)])
    PnL_Realized=numpy.zeros([int(1),int(nPaths)])
    PnL_Unrealized=numpy.zeros([int(1),int(nPaths)])
    momentumRank=numpy.zeros([int(1),int(nPaths)])
    
    riskCapital=numpy.zeros([int(1),int(nPaths)])
    cash=numpy.zeros([int(1),int(nPaths)])
    
    cumulativePnL=numpy.zeros([int(T),int(nPaths)])
    cumulativeRealizedPnL=numpy.zeros([int(T),int(nPaths)])
    cumulativeUnrealizedPnL=numpy.zeros([int(T),int(nPaths)])
    WAC=numpy.zeros([int(T),int(nPaths)])
    equityCurves=numpy.zeros([int(T),int(nPaths)])   
    equityCurve=numpy.zeros([int(T),int(1)])
    closedEquityCurve=numpy.zeros([int(T),int(1)])
    numberOfPositions=numpy.zeros([int(T),int(1)])

    equityCurve[0]=accountSize
    closedEquityCurve[0]=accountSize    
            
    rebalance=0
        
    # iterate over each point in time
    for t in range(1,int(T)):  
        # iterate over each price path
        for pathIndex in range(0,int(nPaths)):
            # ignore indicator build-up period
            if (t == lookback):
                momentumPaths[t,pathIndex]=momentumIndicator[t-1,pathIndex]                      
            elif (t>lookback):           
                #               
                if (rebalance == rebalanceN):
                    momentumPaths[t,pathIndex]=momentumIndicator[t-1,pathIndex]          
                # we are flat
                if (position[t-1,pathIndex] == 0.0):
                    # trend is up and rank is high enough
                    if ( (emaFast[t-1,pathIndex] > emaSlow[t-1,pathIndex]) & (momentumRank[0,pathIndex]<=nPositions) ):
                        # go long
                        position[t,pathIndex]=numpy.floor( ( fPercent*(closedEquityCurve[t-1]) ) / (atr[t-1,pathIndex]*atrMultiplier) )
                        # set initial stop (multiplier x atr) below current price
                        stopLevel[t,pathIndex] = pricePaths[t,pathIndex] - (atr[t-1,pathIndex]*atrMultiplier)
                        #
                        cash[0,pathIndex]=(position[t,pathIndex]*pricePaths[t,pathIndex])*-1
                        #
                        riskCapital[0,pathIndex]=(atr[t-1,pathIndex]*atrMultiplier)*position[t,pathIndex]
                                                
                    # trend is down and rank is high enough
                    elif ( (emaFast[t-1,pathIndex] < emaSlow[t-1,pathIndex]) & (longOnly==False) & (momentumRank[0,pathIndex]<=nPositions) ):
                        # go short
                        position[t,pathIndex]=-numpy.floor( ( fPercent*(closedEquityCurve[t-1]) ) / (atr[t-1,pathIndex]*atrMultiplier) )
                        # place initial stop (multiplier x atr) above current price
                        stopLevel[t,pathIndex] = pricePaths[t,pathIndex] + (atr[t-1,pathIndex]*atrMultiplier)
                        #
                        cash[0,pathIndex]=(position[t,pathIndex]*pricePaths[t,pathIndex])*-1
                        #
                        riskCapital[0,pathIndex]=(atr[t-1,pathIndex]*atrMultiplier)*position[t,pathIndex]
                    
                    else:
                        position[t,pathIndex]=position[t-1,pathIndex]
                                      
                # we have a position
                elif (position[t-1,pathIndex] !=0.0):
                           
                    # if we are long
                    if (position[t-1,pathIndex] > 0.0):
                        
                        # check if price is at or below stop or rank is too low
                        if ((pricePaths[t,pathIndex] <= stopLevel[t-1,pathIndex]) | (momentumRank[0,pathIndex]>nPositions)):
                            #
                            cash[0,pathIndex]=(pricePaths[t,pathIndex]*position[t,pathIndex])
                            # flatten position, clear stop
                            position[t,pathIndex]=0.0
                            #
                            stopLevel[t,pathIndex]=numpy.nan
                            #
                            riskCapital[0,pathIndex]=0                   
                                         
                        # we are not stopped out - maintain position and update stop level
                        else:
                            # maintain the position
                            position[t,pathIndex]=position[t-1,pathIndex]
                                                        
                            # update stop
                            # check if stop should be moved up
                            if ( (pricePaths[t,pathIndex] - (atr[t-1,pathIndex]*atrMultiplier)) > stopLevel[t-1,pathIndex] ):
                                stopLevel[t,pathIndex]=pricePaths[t,pathIndex] - (atr[t-1,pathIndex]*atrMultiplier)
                            # keep stop same
                            else:
                                stopLevel[t,pathIndex]=stopLevel[t-1,pathIndex]     

                    # if we are short
                    elif ((position[t-1,pathIndex] < 0.0) & (longOnly==False)):
                        # check if price is at or above stop or rank is too low
                        if ((pricePaths[t,pathIndex] >= stopLevel[t-1,pathIndex]) | (momentumRank[0,pathIndex]>nPositions)):
                            #
                            cash[0,pathIndex]=-(pricePaths[t,pathIndex]*position[t,pathIndex])                                                        
                            # flatten position, clear stop
                            position[t,pathIndex]=0
                            stopLevel[t,pathIndex]=numpy.nan
                            #
                            riskCapital[0,pathIndex]=0 
                                                       
                        # we are not stopped out maintain the position and update the stop level    
                        else:
                            # maintain the position
                            position[t,pathIndex]=position[t-1,pathIndex]
                                                        
                            # update stop
                            # check if stop should be moved down
                            if ( (pricePaths[t,pathIndex] + (atr[t-1,pathIndex]*atrMultiplier) ) < stopLevel[t-1,pathIndex]):
                                stopLevel[t,pathIndex]=pricePaths[t,pathIndex] + (atr[t-1,pathIndex]*atrMultiplier)
                            # keep the stop same
                            else:
                                stopLevel[t,pathIndex]=stopLevel[t-1,pathIndex]
              
                #
                tradeSize[0,pathIndex] = position[t,pathIndex] - position[t-1,pathIndex]
                
                if (tradeSize[0,pathIndex] != 0.0):
                    tradePrice[0,pathIndex] = pricePaths[t,pathIndex]
                else:
                    tradePrice[0,pathIndex] = 0.0
                
                # determine current liquidation value  
                exitMarkToMarket[0,pathIndex] = pricePaths[t,pathIndex] * position[t,pathIndex]
     
                # P&L
                if(tradeSize[0,pathIndex]==0.0):    
                    PnL_Unrealized[0,pathIndex] = exitMarkToMarket[0,pathIndex] - costOfExposure[0,
                        pathIndex]
                else:
                    if(position[t,pathIndex]==0.0):
                        PnL_Realized[0,pathIndex] = ( tradePrice[0,pathIndex] * position[t-1,pathIndex] - \
                            costOfExposure[0,pathIndex] + PnL_Realized[0,pathIndex] )
                        costOfExposure[0,pathIndex] = 0.0
                        PnL_Unrealized[0,pathIndex] = 0.0
                    else:
                        PnL_Realized[0,pathIndex] = PnL_Realized[0,pathIndex]
                        costOfExposure[0,pathIndex] = costOfExposure[0,pathIndex] + tradePrice[0,pathIndex] * tradeSize[0,pathIndex]
                        PnL_Unrealized[0,pathIndex] = exitMarkToMarket[0,pathIndex] - costOfExposure[0,pathIndex]      
         
                # compute cumulative P&L (realized + unrealized) and store
                cumulativePnL[t,pathIndex] = PnL_Realized[0,pathIndex] + PnL_Unrealized[0,pathIndex]
                cumulativeRealizedPnL[t,pathIndex] = PnL_Realized[0,pathIndex]
                cumulativeUnrealizedPnL[t,pathIndex] = PnL_Unrealized[0,pathIndex]
                WAC[t,pathIndex] = costOfExposure[0,pathIndex]
                # create equity curve
                equityCurves[t,pathIndex]=cumulativePnL[t,pathIndex]+riskCapital[0,pathIndex]

        # sum P&L for each instrument in portfolio
        equityCurve[t]=numpy.sum(cumulativePnL[t,:],axis=0)+accountSize
        # sum realized P&L for each instrument in portfolio
        closedEquityCurve[t]=numpy.sum(cumulativeRealizedPnL[t,:],axis=0)+accountSize
            
        # compute momentum rank
        if ((rebalance == rebalanceN) | (t == lookback)):
            # sort momentum
            momentumIndex=numpy.argsort(momentumPaths[t,:]*-1, axis=0)
            # assign momentum rank
            momentumRank[0,momentumIndex]=numpy.arange(1,nPaths+1)            
            # count number of positions
            numberOfPositions[t]=len(momentumRank[-1,momentumRank[-1,:]<=nPositions])
            # reset rebalance counter
            rebalance=0

        # increment counter
        rebalance=rebalance+1.0                             

    # create output data structure (to make the code more readable)
    strategyOutput=dict()
    # assign output    
    strategyOutput['position']=position
    strategyOutput['stopLevel']=stopLevel
    strategyOutput['atr']=atr
    strategyOutput['emaFast']=emaFast
    strategyOutput['emaSlow']=emaSlow
    strategyOutput['cumulativePnL']=cumulativePnL
    strategyOutput['cumulativeRealizedPnL']=cumulativeRealizedPnL
    strategyOutput['cumulativeUnrealizedPnL']=cumulativeUnrealizedPnL
    strategyOutput['WAC']=WAC
    strategyOutput['quityCurve']=equityCurve
    strategyOutput['momentumPaths']=momentumPaths
    strategyOutput['cash']=cash
    strategyOutput['equityCurves']=equityCurves
    strategyOutput['equityCurve']=equityCurve
    strategyOutput['closedEquityCurve']=closedEquityCurve
    strategyOutput['numberOfPositions']=numberOfPositions
    
    # return output                                                                                   
    return strategyOutput

def openRiskLimit2FPercent(openRiskLimit,nPositionLimit):
    fPercent=openRiskLimit/nPositionLimit
    return fPercent


def saveStrategyOutput2h5(baseDirectory,universeName,instrumentList,strategyInputs,strategyOutput):
    # set HDF5 output file directory
    outputDirectoryH5=baseDirectory+"/strategy/h5/"
    # create directory if it does not exist
    ensureDirectory(outputDirectoryH5)

    # extract key parameters
    atrLookback = str(int(strategyInputs['atrLookback']))
    atrMultiplier = str(int(strategyInputs['atrMultiplier']))
    fastLookback = str(int(strategyInputs['fastLookback']))
    slowLookback = str(int(strategyInputs['slowLookback']))
    momentumLookback = str(int(strategyInputs['momentumLookback']))
    rebalanceN = str(int(strategyInputs['rebalanceN']))
    nPositions = str(int(strategyInputs['nPositions']))
    parameterString=atrLookback+"-"+atrMultiplier+"-"+fastLookback+"-"+slowLookback+"-"+momentumLookback+"-"+rebalanceN+"-"+nPositions
    # create file name
    outputFileNameH5=universeName+"_"+parameterString+'_momentum.h5'
    
    # create HDF5 data store
    data_store = pandas.HDFStore(outputDirectoryH5+outputFileNameH5)
    # store strategy input in HDF5 data store
    parameterNames=['atrLookback','atrMultiplier','fastLookback','slowLookback',
        'momentumLookback','longOnly','accountSize','fPercent','rebalanceN',
        'nPositions']
    parameters=[strategyInputs['atrLookback'],strategyInputs['atrMultiplier'],
        strategyInputs['fastLookback'],strategyInputs['slowLookback'],
        strategyInputs['momentumLookback'],strategyInputs['longOnly'],
        strategyInputs['accountSize'],strategyInputs['fPercent'],
        strategyInputs['rebalanceN'],strategyInputs['nPositions']]
    parameterDf=pandas.DataFrame(index=parameterNames,data=parameters,columns=['parameter'])
    data_store['pricePaths'] = pandas.DataFrame(index=strategyInputs['dateTime'],
        data=strategyInputs['pricePaths'])
    data_store['trueRangePaths'] = pandas.DataFrame(index=strategyInputs['dateTime'],
        data=strategyInputs['trueRangePaths'])
    data_store['parameters'] = parameterDf
    
    # store strategy output in HDF5 data store
    data_store['position'] = pandas.DataFrame(index=strategyInputs['dateTime'],data=strategyOutput['position'])
    data_store['stopLevel'] = pandas.DataFrame(strategyOutput['stopLevel'])
    data_store['atr'] = pandas.DataFrame(strategyOutput['atr'])
    data_store['emaFast'] = pandas.DataFrame(strategyOutput['emaFast'])
    data_store['emaSlow']=pandas.DataFrame(strategyOutput['emaSlow'])
    data_store['cumulativePnL']=pandas.DataFrame(strategyOutput['cumulativePnL'])
    data_store['cumulativeRealizedPnL']=pandas.DataFrame(strategyOutput['cumulativeRealizedPnL'])
    data_store['cumulativeUnrealizedPnL']=pandas.DataFrame(strategyOutput['cumulativeUnrealizedPnL'])
    data_store['WAC']=pandas.DataFrame(strategyOutput['WAC'])
    data_store['equityCurve']=pandas.DataFrame(strategyOutput['equityCurve'])
    data_store['momentumPaths']=pandas.DataFrame(strategyOutput['momentumPaths'])
    data_store['cash']=pandas.DataFrame(strategyOutput['cash'])
    data_store['equityCurves']=pandas.DataFrame(strategyOutput['equityCurves'])
    data_store['equityCurve']=pandas.DataFrame(strategyOutput['equityCurve'])
    data_store['closedEquityCurve']=pandas.DataFrame(strategyOutput['closedEquityCurve'])
    data_store['numberOfPositions']=pandas.DataFrame(strategyOutput['numberOfPositions'])
    # store instrument master
    data_store['instrumentMaster'] = instrumentList
    # close the HDF5 data store
    data_store.close()      
    
    return outputDirectoryH5,outputFileNameH5

inputDirectoryH5='F:/marketData/global_monitoring/csi/data/equity/h5/'
inputFileNameH5="sp1500_csi.h5"

# extract prices
prices = pandas.read_hdf(inputDirectoryH5+inputFileNameH5,'price')
# extract true ranges
trueRanges = pandas.read_hdf(inputDirectoryH5+inputFileNameH5,'trueRange')
# extract instrument master
instrumentMaster = pandas.read_hdf(inputDirectoryH5+inputFileNameH5,'instrumentMaster')
#
startDate='2006-01-01'

#
prices=prices.loc[startDate:]
trueRanges=trueRanges.loc[startDate:]

numberOfObservations=numpy.sum(prices.isnull()==False,axis=0)
#
fullSampleIndex=numberOfObservations==max(numberOfObservations)
#
fullPrices=prices.loc[:,fullSampleIndex]
fullTrueRanges=trueRanges.loc[:,fullSampleIndex]

# strategy parameters
atrLookback=20.0
fastLookback=120.0
slowLookback=150.0
atrMultiplier=8
momentumLookback=90.0
rebalanceN=14.0
longOnly=False
accountSize=1000000.0
openRiskLimit=0.2
nPositions=150
fPercent=openRiskLimit2FPercent(openRiskLimit,nPositions)

strategyInputs=dict()
strategyInputs['dateTime']=fullPrices.index
strategyInputs['pricePaths']=fullPrices.values
strategyInputs['trueRangePaths']=fullTrueRanges.values
strategyInputs['atrLookback']=atrLookback
strategyInputs['atrMultiplier']=atrMultiplier
strategyInputs['fastLookback']=fastLookback
strategyInputs['slowLookback']=slowLookback
strategyInputs['momentumLookback']=momentumLookback
strategyInputs['longOnly']=longOnly
strategyInputs['accountSize']=accountSize
strategyInputs['fPercent']=fPercent
strategyInputs['rebalanceN']=rebalanceN
strategyInputs['nPositions']=nPositions
# simulate strategy
strategyOutput=momentumCrossoverWithStop(strategyInputs)

# extract output
position=strategyOutput['position']
stopLevel=strategyOutput['stopLevel']
atr=strategyOutput['atr']
emaFast=strategyOutput['emaFast']
emaSlow=strategyOutput['emaSlow']
cumulativePnL=strategyOutput['cumulativePnL']
cumulativeRealizedPnL=strategyOutput['cumulativeRealizedPnL']
cumulativeUnrealizedPnL=strategyOutput['cumulativeUnrealizedPnL']
WAC=strategyOutput['WAC']
equityCurve=strategyOutput['quityCurve']
momentumPaths=strategyOutput['momentumPaths']
cash=strategyOutput['cash']
equityCurves=strategyOutput['equityCurves']
equityCurve=strategyOutput['equityCurve']
closedEquityCurve=strategyOutput['closedEquityCurve']
numberOfPositions=strategyOutput['numberOfPositions']
#
twr=pandas.DataFrame(index=prices.index,data=equityCurve/accountSize,columns=['TWR'])

universeName="SP1500"

baseDirectory="F:/marketData/global_monitoring/csi/data/equity/"

strategyDirectoryH5,strategyFileNameH5=saveStrategyOutput2h5(baseDirectory,
    universeName,instrumentMaster,strategyInputs,strategyOutput)
