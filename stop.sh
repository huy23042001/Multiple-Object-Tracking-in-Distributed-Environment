cd /usr/local/hadoop
#Format hệ thống
# yes | hdfs namenode -format
#Run hệ thống Hadoop
sbin/stop-all.sh
#Run Job History
sbin/mr-jobhistory-daemon.sh stop historyserver

# hdfs dfs -mkdir -p spark-logs
# hdfs dfs -chown -R hduser:hadoop spark-logs

# hdfs dfs -mkdir -p spark-events
# hdfs dfs -chown -R hduser:hadoop spark-events
#start zookeeper
cd /usr/local/zookeeper
bin/zkServer.sh stop

#start spark
cd /usr/local/spark
sbin/stop-all.sh