#!/bin/bash
rm -rf data.etcd
export ETCDCTL_API=3

if [ $# -eq 0 ]
then
    echo "Usage: $0 MACHINE_NUM"
    exit 1
fi

TOKEN=k8sonbudget
CLUSTER_STATE=new
NAME_1=vm-116
NAME_2=vm-117
NAME_3=vm-118
HOST_1=10.140.17.116 
HOST_2=10.140.17.117 
HOST_3=10.140.17.118 
CLUSTER=${NAME_1}=http://${HOST_1}:2380,${NAME_2}=http://${HOST_2}:2380,${NAME_3}=http://${HOST_3}:2380
export ENDPOINTS=$HOST_1:2379,$HOST_2:2379,$HOST_3:2379

if [ $1 -eq 1 ]
then
    # For machine 1
    THIS_NAME=${NAME_1}
    THIS_IP=${HOST_1}
elif [ $1 -eq 2 ]
then
    # For machine 2
    THIS_NAME=${NAME_2}
    THIS_IP=${HOST_2}
elif [ $1 -eq 3 ]
then
    # For machine 3
    THIS_NAME=${NAME_3}
    THIS_IP=${HOST_3}
else
    echo "MACHINE_NUM out of bound"
    exit 1
fi

echo "Starting etcd on ${THIS_NAME} with IP ${THIS_IP}"

etcd --data-dir=data.etcd --name ${THIS_NAME} \
	--initial-advertise-peer-urls http://${THIS_IP}:2380 --listen-peer-urls http://${THIS_IP}:2380 \
	--advertise-client-urls http://${THIS_IP}:2379 --listen-client-urls http://${THIS_IP}:2379 \
	--initial-cluster ${CLUSTER} \
	--initial-cluster-state ${CLUSTER_STATE} --initial-cluster-token ${TOKEN}