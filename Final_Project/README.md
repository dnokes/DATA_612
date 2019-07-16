# DATA 612

Applications of matrix factorization are ubiquitous in modern data-driven science. The need for tools that can map a high-dimensional space into a lower-dimensional space continually grows as the amount of data we collect increases.

A service like Spotify has subscribers that provide indications of interest in particular content in the catalog by either listening to particular items, clicking on items to read descriptions, or adding items to a playlist. Such implicit ratings data allows recommender systems developers to create the classic user by item by implicit rating matrix and apply collaborative filtering. Similarly, trading systems researchers potentially have a very large set of distinct systems that select instruments from a particular instrument universe. The portfolio of positions - which varies over time - provides an indication of the kind of positions each system ‘likes’. Many systems traders run ensembles comprised of multiple instances of the same system and instrument universe with different parameter sets. The more diverse the systems within the ensemble (i.e., the lower the co-movement between portfolio components) the faster the return compounding. For the systems researcher, despite knowing the underlying mechanism for selecting instruments, it is not always easy to group systems in such a way as to maximize the diversity within the total portfolio.

The output data for this project can be found here:

https://www.dropbox.com/sh/nxe7f1l8n4bukrr/AABf8eo0G43uClDmftfiGnYfa?dl=0

sp1500.h5: S&P1500 price and instrument master data

SP1500_correlation_v2.h5: S&P1500 rolling correlations

eigenvaluesByDate_subset.h5: S&P1500 eigenvalues by date

proportionOfVarianceByDate_subset.h5: S&P1500 proportion of variance by date

participationRatioByDate_subset.h5: S&P1500 participation ratio by date

Files of the following format are trading system simulator output files:

SP1500_20-6-120-180-90-5-20-40-75_momentum.h5

Each of these files contains data for a classical momentum strategy with a particular set of parameters.

To get the docker environment:

docker pull dgn2/data_612_dev:version1

nvidia-docker run -p 8888:8888 -it -v /local_path/:/docker_container_path/

pull the project (in addition to the rest of the course work) down from github:

[sudo] git clone https://github.com/dnokes/DATA_612.git

Start the Jupyter notebook:

jupyter notebook --ip=0.0.0.0 --allow-root

Navigate to:

http://127.0.0.1:8888/tree



