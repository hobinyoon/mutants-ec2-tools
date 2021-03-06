#!/usr/bin/env python

import boto3
import botocore
import inspect
import json
import math
import os
import pprint
import random
import sys
import time
import types

sys.path.insert(0, "%s/lib/util" % os.path.dirname(__file__))
import Cons
import Util

sys.path.insert(0, "%s/lib" % os.path.dirname(__file__))
import Ec2Region

import LaunchOnDemandInsts
import ReqSpotInsts


def main(argv):
  job_list = []
  for k, v in globals().iteritems():
    if type(v) != types.FunctionType:
      continue
    if k.startswith("Job_"):
      job_list.append(k[4:])
  #Cons.P(job_list)

  if len(argv) != 2:
    Cons.P("Usage: %s job_name" % argv[0])
    Cons.P("  Jobs available:")
    Cons.P(Util.Indent("\n".join(sorted(job_list)), 4))
    sys.exit(1)

  job = "Job_" + argv[1]

  # http://stackoverflow.com/questions/3061/calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python
  globals()[job]()


def Job_Mutant_QuizUp():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      , "rocksdb": {}
      , "ycsb-runs": None
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "false"
      }

  qz_run = {
      # Use the current function name since you always forget to set this
      "exp_desc": inspect.currentframe().f_code.co_name[4:]

      , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
      , "db_stg_devs": [
          ["/mnt/local-ssd0/rocksdb-data/quizup/t0", 0.528]
          , ["/mnt/ebs-st1/rocksdb-data-t1", 0.045]
          ]

      , "record_size": 5000
      , "use_90p_loaded_db": "false"

      , "evict_cached_data": "true"
      , "memory_limit_in_mb": 5.0 * 1024

      # SSTable metadata organization
      , "cache_filter_index_at_all_levels": "false"

      , "monitor_temp": "true"
      , "migrate_sstables": "true"

      # List of (simulation_time_in_sec, workload_end_relative_time)
      #   This should be good for making a snapshot
      #, "workload_time_range": [(0, 0.0), (600, 0.9), (100, 0.91)]
      #
      # To see if it's working
      , "workload_time_range": [(0, 0.0), (30, 0.01), (10, 0.02)]

      , "simulation_time_dur_in_sec": 600

      , "target_cost": 0.4
      , "migration_resistance": 0.05

      # Run the workload super slow after 90% to 91% for taking a snapshot.

      # For taking a snapshot. Wait... is this a good idea? I don't think so. Make it run super slow after 90%.
      , "extra_time_after_playing_the_workload": 600

      , "upload_result_to_s3": "false"
      }
  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  LaunchJob(params)


def Job_Mutant_Seamless_Cost_Perf_Ycsb_D():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/ebs-st1/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  cost_slo = "0.4"

  cost_slo_epsilon = 0.05

  # It takes about an hour to fill the filesystem cache with target_iops 1000.
  #   Let's go with 4000. It will take 15 mins. Ok. Not too bad.
  target_iops_set = [4000, 3000, 2000, 1000]

  cost_changes_set = [
      "15 0.2, 30 0.3"
      , "15 0.3, 30 0.35"]

  op_cnt = 4000 * 45 * 60

  for target_iops in target_iops_set:
    # Run for 45 mins
    #   Operation count shouldn't change to fill up the file system cache. Hmm.
    #op_cnt = target_iops * 45 * 60

    for cost_changes in cost_changes_set:
      ycsb_runs["runs"] = []
      ycsb_runs["runs"].append({
        "load": {
          "use_preloaded_db": [
            "ycsb/%s-%s/ls" % (workload_type, cost_slo),
            "ycsb/%s-%s/est1" % (workload_type, cost_slo)]
          , "ycsb_params": " -p recordcount=10000000"
          # 10 M records. 1 K each. Expect 10 GB of data.
          # 100. When you specify 10, YCSB doesn't stop.
          }
        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
          }

        , "mutant_options": {
          "monitor_temp": "true"
          , "calc_sst_placement": "true"
          , "migrate_sstables": "true"
          # Storage cost SLO. [0.045, 0.528] $/GB/month
          , "stg_cost_slo": float(cost_slo)
          # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
          , "stg_cost_slo_epsilon": cost_slo_epsilon
          , "cache_filter_index_at_all_levels": "false"
          , "db_stg_devs": ycsb_runs["db_stg_devs"]
          , "cost_changes": cost_changes
          }
        })
      params["ycsb-runs"] = dict(ycsb_runs)
      LaunchJob(params)


def Job_Mutant_Ycsb_B():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "b"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/ebs-st1/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  # Measure the max throughput
  if False:
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": ""
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": "ycsb/%s" % workload_type
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      # Catch up with pending compactions
      #, "run": {
      #  "ycsb_params": " -p recordcount=10000000 -p operationcount=10000 -p readproportion=1.0 -p updateproportion=0.0 -target 50"
      #  }

      # Measure max throughput:
      #   RocksDB with local SSD: 55 K
      #   RocksDB with EBS st1: 1440
      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=15000000 -p readproportion=0.95 -p updateproportion=0.05"
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "cache_filter_index_at_all_levels": "false"
        , "db_stg_devs": ycsb_runs["db_stg_devs"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)
    return

  op_cnt = 15000000
  # With 5% writes, 750,000 * 1K = 750 M. So like 11 or 12 new L0 SSTables are flushed, triggering some compactions.

  # Wait. With Mutant, you can't load and run, cause when you run all SSTables will be hot at first.

  for target_iops in [3000]:
    ycsb_runs["runs"] = []
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": ""
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": "ycsb/%s" % workload_type
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p updateproportion=0.05 -target %d" % (op_cnt, target_iops)
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "true"
        , "migrate_sstables": "true"
        # Storage cost SLO. [0.045, 0.528] $/GB/month
        , "stg_cost_slo": 0.4
        , "cache_filter_index_at_all_levels": "false"
        # Evaluating the metadata organization
        #, "cache_filter_index_at_all_levels": "true"

        , "db_stg_devs": ycsb_runs["db_stg_devs"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


def Job_Mutant_Ycsb_D_MeasureCpuOverhead():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": []
      #, "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/local-ssd0/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  cost_slo = "0.333333"
  opcnt_tioses = {
      333333333: [10000]
      }

  # 1000000000: [30000]
  # 1,000,000,000
  #   Expects  50 GB = 1 B (ops) * 0.05 (inserts) * 1KB (record size)
  #   Total size was 172 GB
  #   This saturated CPU as well. Go a lot slower and fewer number of records.

  cost_slo_epsilon=0.1

  for op_cnt, v in sorted(opcnt_tioses.iteritems()):
    for target_iops in v:
      for i in range(10):
        ycsb_runs["runs"] = []
        ycsb_runs["runs"].append({
          "load": {
            "use_preloaded_db": None
            # 100. When you specify 10, YCSB doesn't stop.
            , "ycsb_params": " -p recordcount=100"
            }
          , "run": {
            "evict_cached_data": "true"
            , "memory_limit_in_mb": 5.0 * 1024
            , "ycsb_params": " -p recordcount=100 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
            }

          , "mutant_options": {
            "monitor_temp": "false"
            , "calc_sst_placement": "false"
            , "migrate_sstables": "false"
            # Storage cost SLO. [0.045, 0.528] $/GB/month
            , "stg_cost_slo": float(cost_slo)
            # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
            , "stg_cost_slo_epsilon": cost_slo_epsilon
            , "cache_filter_index_at_all_levels": "false"
            , "db_stg_devs": ycsb_runs["db_stg_devs"]
            }
          })
        params["ycsb-runs"] = dict(ycsb_runs)
        LaunchJob(params)

        ycsb_runs["runs"] = []
        ycsb_runs["runs"].append({
          "load": {
            "use_preloaded_db": None
            # 100. When you specify 10, YCSB doesn't stop.
            , "ycsb_params": " -p recordcount=100"
            }
          , "run": {
            "evict_cached_data": "true"
            , "memory_limit_in_mb": 5.0 * 1024
            , "ycsb_params": " -p recordcount=100 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
            }

          , "mutant_options": {
            "monitor_temp": "true"
            , "calc_sst_placement": "true"
            , "migrate_sstables": "false"
            # Storage cost SLO. [0.045, 0.528] $/GB/month
            , "stg_cost_slo": float(cost_slo)
            # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
            , "stg_cost_slo_epsilon": cost_slo_epsilon
            , "cache_filter_index_at_all_levels": "false"
            , "db_stg_devs": ycsb_runs["db_stg_devs"]
            }
          })
        params["ycsb-runs"] = dict(ycsb_runs)
        LaunchJob(params)


# For the SSTable IO overheads, use 2 local SSDs to see how many extra SSTable movements are there.
def Job_Mutant_Ycsb_D_MeasureIoOverhead():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": []
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/local-ssd0/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  #cost_slo = "0.3"
  # Signifies the baseline experiment
  cost_slo = "0.333333333"
  opcnt_tioses = {
      333333333: [10000]
      # Run faster to verify if it's working
      #333333333: [40000]
      }

  cses = [0.1]
  for cost_slo_epsilon in cses:
    for op_cnt, v in sorted(opcnt_tioses.iteritems()):
      for target_iops in v:
        ycsb_runs["runs"] = []
        ycsb_runs["runs"].append({
          "load": {
            "use_preloaded_db": None
            # 100. When you specify 10, YCSB doesn't stop.
            , "ycsb_params": " -p recordcount=100"
            }
          , "run": {
            "evict_cached_data": "true"
            , "memory_limit_in_mb": 5.0 * 1024
            , "ycsb_params": " -p recordcount=100 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
            }

          , "mutant_options": {
            "monitor_temp": "true"
            , "calc_sst_placement": "true"
            , "migrate_sstables": "false"
            # Storage cost SLO. [0.045, 0.528] $/GB/month
            , "stg_cost_slo": float(cost_slo)
            # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
            , "stg_cost_slo_epsilon": cost_slo_epsilon
            , "cache_filter_index_at_all_levels": "false"
            , "db_stg_devs": ycsb_runs["db_stg_devs"]
            }
          })
        params["ycsb-runs"] = dict(ycsb_runs)
        LaunchJob(params)


def Job_Mutant_Ycsb_D_MeasureIoOverheadByCostSloEpsilons():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": []
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/local-ssd0/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  cost_slo = "0.3"
  opcnt_tioses = {
      333333333: [10000]
      }

  #cses = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09
  #    , 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
  #cses = [0.08]
  #cses = [0.08, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19]
  #cses = [0.04]
  cses = [0.17]
  for cost_slo_epsilon in cses:
    for op_cnt, v in sorted(opcnt_tioses.iteritems()):
      for target_iops in v:
        ycsb_runs["runs"] = []
        ycsb_runs["runs"].append({
          "load": {
            "use_preloaded_db": None
            # 100. When you specify 10, YCSB doesn't stop.
            , "ycsb_params": " -p recordcount=100"
            }
          , "run": {
            "evict_cached_data": "true"
            , "memory_limit_in_mb": 5.0 * 1024
            , "ycsb_params": " -p recordcount=100 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
            }

          , "mutant_options": {
            "monitor_temp": "true"
            , "calc_sst_placement": "true"
            , "migrate_sstables": "true"
            # Storage cost SLO. [0.045, 0.528] $/GB/month
            , "stg_cost_slo": float(cost_slo)
            # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
            , "stg_cost_slo_epsilon": cost_slo_epsilon
            , "cache_filter_index_at_all_levels": "false"
            , "db_stg_devs": ycsb_runs["db_stg_devs"]
            }
          })
        params["ycsb-runs"] = dict(ycsb_runs)
        LaunchJob(params)


def Job_Mutant_Ycsb_D():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/ebs-st1/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  #op_cnt = 15000000
  # With 5% writes, 750,000 * 1K = 750 M. So like 11 or 12 new L0 SSTables are flushed, triggering some compactions.

  #cost_slo = "0.1"
  #target_iopses = [1000, 1500, 2000, 2500, 3000, 3100, 3200, 3300, 3400, 3500]
  # Trying to see when the system saturates
  #target_iopses = [3600, 3700, 3800, 3900, 4000, 5000]
  #target_iopses = [4100, 4200, 4300, 4400]
  #target_iopses = [4500, 4600]
  # Saturated from 4700

  #cost_slo = "0.2"
  #opcnt_tioses = {
  #    #  15000000: [1000, 1500, 2000]
  #    #, 30000000: [3000, 4000, 5000, 6000, 6200, 6400, 6600, 6800]
  #    }
  # Saturated from 7000

  #cost_slo = "0.3"
  #opcnt_tioses = {
      #  15000000: [1000, 2000, 3000]
      #, 30000000: [4000, 5000, 6000]
      #, 40000000: [7000, 8000, 9000, 10000, 11000]
      #40000000: [9100]
      #40000000: [9100, 9200, 9300, 9400, 9500, 9600, 9700, 9800, 9900]
  #    }

  #cost_slo = "0.4"
  #opcnt_tioses = {
      #  15000000: [1000]
      #, 40000000: [5000, 10000, 17000]
  #    40000000: [17200, 17400, 17600, 17800]
  #    }
  #Saturated from 18000

  #cost_slo = "0.5"
  #target_iopses = [1000, 5000, 10000, 15000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
  #target_iopses = [60000]
  #target_iopses = [62000, 64000, 66000, 68000]
  # Saturated from 70000

  # Measure the max throughput
  #   With the cost SLO of 0.4: 23 K. Should try up to 25 K
  #   Get the other DB snapshots ready too: [0.045, 0.528]
  #     0.1 done
  #     0.2 done. well. a lot of shuffling. let's just go. Do the same target IOPSes as 0.3
  #     0.3 done
  #     0.4 done
  #     0.5 done
  if False:
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": None
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": [
          "ycsb/%s-%s/ls" % (workload_type, cost_slo),
          "ycsb/%s-%s/est1" % (workload_type, cost_slo)]
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      # Catch up with pending compactions
      , "run": {
        "ycsb_params": " -p recordcount=10000000 -p operationcount=200000 -p readproportion=1.0 -p insertproportion=0.0 -target 1000"
        }

      # Measure max throughput
      #, "run": {
      #  "evict_cached_data": "true"
      #  , "memory_limit_in_mb": 5.0 * 1024
      #  # Need to specify the target. Without it EBS st1 saturates and migrations don't happen.
      #  , "ycsb_params": " -p recordcount=10000000 -p operationcount=15000000 -p readproportion=0.95 -p insertproportion=0.05 "
      #  }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "true"
        , "migrate_sstables": "true"
        # Storage cost SLO. [0.045, 0.528] $/GB/month
        , "stg_cost_slo": float(cost_slo)
        # Hysteresis range.
        #   It has to be 0.0 when catching up the pending copactions. Otherwise too wide movement with the target 50
        #   It can be 0.1 when measuring the max throughput.
        , "stg_cost_slo_epsilon": 0.0
        , "cache_filter_index_at_all_levels": "false"
        # Evaluating the metadata organization
        #, "cache_filter_index_at_all_levels": "true"
        , "db_stg_devs": ycsb_runs["db_stg_devs"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)
    return

  cost_slo_epsilon=0.1

  for op_cnt, v in sorted(opcnt_tioses.iteritems()):
    for target_iops in v:
      ycsb_runs["runs"] = []
      ycsb_runs["runs"].append({
        "load": {
          #"use_preloaded_db": None
          # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
          "use_preloaded_db": [
            "ycsb/%s-%s/ls" % (workload_type, cost_slo),
            "ycsb/%s-%s/est1" % (workload_type, cost_slo)]
          , "ycsb_params": " -p recordcount=10000000"
          # 10 M records. 1 K each. Expect 10 GB of data.
          }

        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
          }

        , "mutant_options": {
          "monitor_temp": "true"
          , "migrate_sstables": "true"
          # Storage cost SLO. [0.045, 0.528] $/GB/month
          , "stg_cost_slo": float(cost_slo)
          # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
          , "stg_cost_slo_epsilon": cost_slo_epsilon
          , "cache_filter_index_at_all_levels": "false"
          , "db_stg_devs": ycsb_runs["db_stg_devs"]
          }
        })
      params["ycsb-runs"] = dict(ycsb_runs)
      LaunchJob(params)


def Job_Mutant_MetaDataOrg_Ycsb_D():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/local-ssd0/rocksdb-data/ycsb/t0", 0.528]
        , ["/mnt/ebs-st1/rocksdb-data-t1", 0.045]
        ]
    , "runs": []
    }

  #op_cnt = 15000000
  # With 5% writes, 750,000 * 1K = 750 M. So like 11 or 12 new L0 SSTables are flushed, triggering some compactions.

  #cost_slo = "0.1"
  #opcnt_tioses = {
  #      15000000: [1000, 1500, 2000, 2500, 3000]
  #    , 30000000: [3500, 4000]
  #    , 40000000: [4600, 4800, 5000]
  #    }

  #cost_slo = "0.2"
  #opcnt_tioses = {
      #  15000000: [1000, 2000]
      #, 30000000: [3000, 4000]
      #, 40000000: [4500]
      #40000000: [5000, 6000, 6200, 6400, 6600, 6800, 7000]
      #}

  #cost_slo = "0.3"
  #opcnt_tioses = {
  #    #  15000000: [1000, 2000]
  #    #, 30000000: [3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000]
      # 30000000: [7000, 8000, 9000, 10000, 11000, 12000]
      # 40000000: [8200, 8500,  9000, 9500, 10000, 15000, 20000]
  #    }

  cost_slo = "0.4"
  opcnt_tioses = {
      #  15000000: [1000]
      #, 30000000: [5000, 10000]
      #, 40000000: [15000, 20000, 30000, 40000, 50000]
      40000000: [16000, 17000, 18000, 19000]
      }

  #cost_slo = "0.5"
  #opcnt_tioses = {
  #      15000000: [1000]
  #    , 30000000: [5000, 10000]
  #    , 40000000: [20000, 30000, 40000, 50000, 60000, 70000]
  #    , 40000000: [72000, 74000, 76000, 78000, 80000, 85000, 90000, 95000]
  #    , 40000000: [96000, 97000, 98000, 99000]
  #    }
  # Saturated at 99000

  # Measure the max throughput
  #   With the cost SLO of 0.4: 23 K. Should try up to 25 K
  #   Get the other DB snapshots ready too: [0.045, 0.528]
  #     0.1 done
  #     0.2 done. well. a lot of shuffling. let's just go. Do the same target IOPSes as 0.3
  #     0.3 done
  #     0.4 done
  #     0.5 done
  if False:
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": None
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": [
          "ycsb/%s-%s/ls" % (workload_type, cost_slo),
          "ycsb/%s-%s/est1" % (workload_type, cost_slo)]
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      # Catch up with pending compactions
      , "run": {
        "ycsb_params": " -p recordcount=10000000 -p operationcount=200000 -p readproportion=1.0 -p insertproportion=0.0 -target 1000"
        }

      # Measure max throughput
      #, "run": {
      #  "evict_cached_data": "true"
      #  , "memory_limit_in_mb": 5.0 * 1024
      #  # Need to specify the target. Without it EBS st1 saturates and migrations don't happen.
      #  , "ycsb_params": " -p recordcount=10000000 -p operationcount=15000000 -p readproportion=0.95 -p insertproportion=0.05 "
      #  }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "true"
        , "migrate_sstables": "true"
        # Storage cost SLO. [0.045, 0.528] $/GB/month
        , "stg_cost_slo": float(cost_slo)
        # Hysteresis range.
        #   It has to be 0.0 when catching up the pending copactions. Otherwise too wide movement with the target 50
        #   It can be 0.1 when measuring the max throughput.
        , "stg_cost_slo_epsilon": 0.0
        , "cache_filter_index_at_all_levels": "false"
        # Evaluating the metadata organization
        #, "cache_filter_index_at_all_levels": "true"
        , "db_stg_devs": ycsb_runs["db_stg_devs"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)
    return

  cost_slo_epsilon=0.1

  for op_cnt, v in sorted(opcnt_tioses.iteritems()):
    for target_iops in v:
      ycsb_runs["runs"] = []
      ycsb_runs["runs"].append({
        "load": {
          #"use_preloaded_db": None
          # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
          "use_preloaded_db": [
            "ycsb/%s-%s/ls" % (workload_type, cost_slo),
            "ycsb/%s-%s/est1" % (workload_type, cost_slo)]
          , "ycsb_params": " -p recordcount=10000000"
          # 10 M records. 1 K each. Expect 10 GB of data.
          }

        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
          }

        , "mutant_options": {
          "monitor_temp": "true"
          , "migrate_sstables": "true"
          # Storage cost SLO. [0.045, 0.528] $/GB/month
          , "stg_cost_slo": float(cost_slo)
          # Hysteresis range. 0.1 of the SSTables near the sst_ott don't get migrated.
          , "stg_cost_slo_epsilon": cost_slo_epsilon
          , "cache_filter_index_at_all_levels": "true"
          , "db_stg_devs": ycsb_runs["db_stg_devs"]
          }
        })
      params["ycsb-runs"] = dict(ycsb_runs)
      LaunchJob(params)


def Job_Rocksdb_Ycsb_D_EbsSt1():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/ebs-st1/rocksdb-data/ycsb"
    , "db_stg_devs": [
        ["/mnt/ebs-st1/rocksdb-data/ycsb/t0", 0.045]
        ]
    , "runs": []
    }

  # Measure the max throughput
  if False:
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": None
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": ["ycsb/%s-ebsst1" % workload_type]
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      # Catch up with pending compactions
      #, "run": {
      #  "ycsb_params": " -p recordcount=10000000 -p operationcount=20000 -p readproportion=1.0 -p insertproportion=0.0 -target 50"
      #  }

      # Measure max throughput. It's super slow in the beginning and stabilized when the filesystem cache is full.
      #   Check the cache size from dstat log
      #   Around 8000 IOPS. A lot higher than what YCSB reports since it includes the initial slow period.
      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=15000000 -p readproportion=0.95 -p insertproportion=0.05"
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "cache_filter_index_at_all_levels": "false"
        , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)
    return

  op_cnt = 15000000
  # With 5% writes, 750,000 * 1K = 750 M. So like 11 or 12 new L0 SSTables are flushed, triggering some compactions.

  #target_iopses = [1000, 1500, 2000, 2500, 3000, 3100, 3200, 3300, 3400, 3500]
  #target_iopses = [1500, 2000, 2500, 3000, 3100, 3200, 3300, 3400, 3500]
  #target_iopses = [3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000]
  target_iopses = [3400]
  op_cnt = 30000000

  for target_iops in target_iopses:
    ycsb_runs["runs"] = []
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": None
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": ["ycsb/%s-ebsst1" % workload_type]
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "cache_filter_index_at_all_levels": "false"
        # Evaluate the metadata organization
        #, "cache_filter_index_at_all_levels": "true"
        , "db_stg_devs": ycsb_runs["db_stg_devs"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


def Job_Rocksdb_Ycsb_D():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": []
      #, "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": {}
      , "ycsb-runs": {}
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  workload_type = "d"

  ycsb_runs = {
    "exp_desc": inspect.currentframe().f_code.co_name[4:]
    , "workload_type": workload_type
    , "db_path": "/mnt/local-ssd0/rocksdb-data/ycsb"
    , "db_stg_dev_paths": [
        "/mnt/local-ssd0/rocksdb-data/ycsb/t0"
        ]
    , "runs": []
    }

  # Measure the max throughput
  if False:
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": ""
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": "ycsb/%s" % workload_type
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      # Catch up with pending compactions
      #, "run": {
      #  "ycsb_params": " -p recordcount=10000000 -p operationcount=10000 -p readproportion=1.0 -p insertproportion=0.0 -target 50"
      #  }

      # Measure max throughput: 130000
      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=15000000 -p readproportion=0.95 -p insertproportion=0.05"
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "cache_filter_index_at_all_levels": "false"
        , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)
    return

  op_cnt = 15000000
  # With 5% writes, 750,000 * 1K = 750 M. So like 11 or 12 new L0 SSTables are flushed, triggering some compactions.

  for target_iops in [
          1000
      ,   5000
      ,  10000
      ,  20000
      ,  30000
      ,  40000
      ,  50000
      ,  60000
      ,  70000
      ,  80000
      ,  90000
      , 100000
      , 110000
      , 120000
      , 130000]:
    ycsb_runs["runs"] = []
    ycsb_runs["runs"].append({
      "load": {
        #"use_preloaded_db": ""
        # This saves time. 1m 35sec instead of like 5m + pending SSTable compaction time, which can take like 5 mins.
        "use_preloaded_db": "ycsb/%s" % workload_type
        , "ycsb_params": " -p recordcount=10000000"
        # 10 M records. 1 K each. Expect 10 GB of data.
        }

      , "run": {
        "evict_cached_data": "true"
        , "memory_limit_in_mb": 5.0 * 1024
        , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
        }

      # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
      , "mutant_options": {
        "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "sst_ott": 0
        , "cache_filter_index_at_all_levels": "false"
        # Evaluating the metadata organization
        #, "cache_filter_index_at_all_levels": "true"
        , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
        }
      })
    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


def Job_StgDevPerf():
  params = {
      "region": "us-east-1"
      , "inst_type": "r3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": []
      #, "block_storage_devs": [{"VolumeType": "gp2", "VolumeSize": 200, "DeviceName": "d"}]
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      #, "block_storage_devs": [{"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      #, "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      #, "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "false"
      }
  LaunchJob(params)


# A workload type per an EC2 instance for now, but nothing's stopping you running different types of workloads in an instance.
def Job_Ycsb_D_Mutant():
  # Job conf per EC2 inst
  class ConfEc2Inst:
    exp_per_ec2inst = 31

    def __init__(self):
      self.params = []
    def Full(self):
      return (len(self.params) >= ConfEc2Inst.exp_per_ec2inst)
    def Add(self, params):
      self.params.append(params)
    def Size(self):
      return len(self.params)
    def __repr__(self):
      return "%s" % (self.params)

  workload_type = "d"
  slow_stg_dev = "ebs-st1"

  # SSTable OTT (organization temperature threshold)
  # Target IOPSes
  sstott_targetiops = {
      2**(-12): [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(-10): [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(-8):  [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(-6):  [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(-4):  [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(-2):  [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(0):   [1000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000]
    , 2**(12): [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    , 2**(14): [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    , 2**(16): [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    , 2**(18): [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    }
  for sst_ott, targetiops in sstott_targetiops.iteritems():
    random.shuffle(sstott_targetiops[sst_ott])

  confs_ec2 = []
  conf_ec2 = ConfEc2Inst()
  for i in range(5):
    for sst_ott, targetiops in sorted(sstott_targetiops.iteritems()):
      for ti in targetiops:
        if conf_ec2.Full():
          confs_ec2.append(conf_ec2)
          conf_ec2 = ConfEc2Inst()
        conf_ec2.Add((ti, sst_ott))
  if conf_ec2.Size() > 0:
    confs_ec2.append(conf_ec2)

  Cons.P("%d machine(s)" % len(confs_ec2))
  Cons.P(pprint.pformat(confs_ec2, width=100))
  sys.exit(1)

  for conf_ec2 in confs_ec2:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        , "init_script": "mutant-rocksdb"
        , "ami_name": "mutant-rocksdb"
        , "block_storage_devs": []
        , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
        # Initialize local SSD by erasing. Some EC2 instance types need this.
        , "erase_local_ssd": "true"
        , "unzip_quizup_data": "false"
        , "run_cassandra_server": "false"
        , "rocksdb": {}  # This doesn't do much other than checking out the code and building.
        , "rocksdb-quizup-runs": []
        , "ycsb-runs": []
        , "terminate_inst_when_done": "true"
        }
    if slow_stg_dev == "ebs-st1":
      # 40 MiB/s/TiB. With 3 TiB, 120 MiB/sec.
      #   This should be good enough.
      #     With a local SSD experiment, the average throughput tops at 35 MB/s. Although 99th percentile goes up to 260 MB/s.
      #     You can check with the dstat local ssd log.
      #     However, the saturation happens way earlier than that. Check with the experiment results.
      #   However, regardless of the throughput number, st1 is really slow in practice.
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    else:
      raise RuntimeError("Unexpected")

    ycsb_runs = {
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "workload_type": workload_type
      , "db_path": "/mnt/local-ssd1/rocksdb-data/ycsb"
      , "db_stg_dev_paths": [
          "/mnt/local-ssd1/rocksdb-data/ycsb/t0"
          , "/mnt/%s/rocksdb-data-t1" % slow_stg_dev]
      , "runs": []
      }

    # TODO: I'm concerned about the initial bulk SSTable migration. Or should I?
    #   We'll see the result and think about it. We'll have to gather all raw log files.
    #   If that's the case, we'll have to exclude the initial warm up period.
    for p in conf_ec2.params:
      target_iops = p[0]
      sst_ott = p[1]
      op_cnt = 10000000 / 2
      if target_iops < 10000:
        op_cnt = op_cnt / 10
      ycsb_runs["runs"].append({
        "load": {
          #"use_preloaded_db": ""
          "use_preloaded_db": "ycsb-%s-10M-records-rocksdb" % workload_type
          , "ycsb_params": " -p recordcount=10000000 -target 10000"
          }
        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=%d -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
          }
        # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
        , "mutant_options": {
          "monitor_temp": "true"
          , "migrate_sstables": "true"
          , "sst_ott": sst_ott
          , "cache_filter_index_at_all_levels": "true"
          # Replaying a workload in the past
          #, "replaying": {
          #  "simulated_time_dur_sec": 1365709.587
          #  , "simulation_time_dur_sec": 60000
          #  }
          , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
          }
        })

    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


def Job_Ycsb_A_Rocksdb():
  # Job conf per EC2 inst
  class ConfEc2Inst:
    exp_per_ec2inst = 4

    def __init__(self):
      self.params = []
    def Full(self):
      return (len(self.params) >= ConfEc2Inst.exp_per_ec2inst)
    def Add(self, params):
      self.params.append(params)
    def Size(self):
      return len(self.params)
    def __repr__(self):
      return "%s" % (self.params)

  workload_type = "a"

  db_stg_dev = "ebs-st1"
  #db_stg_dev = "local-ssd1"

  if db_stg_dev == "local-ssd1":
    target_iops_range = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000 \
        , 11000, 12000, 13000, 14000, 15000, 16000, 17000, 18000, 19000, 20000]
  elif db_stg_dev == "ebs-st1":
    target_iops_range = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
  random.shuffle(target_iops_range)

  confs_ec2 = []
  conf_ec2 = ConfEc2Inst()
  for i in range(5):
    for ti in target_iops_range:
      if conf_ec2.Full():
        confs_ec2.append(conf_ec2)
        conf_ec2 = ConfEc2Inst()
      conf_ec2.Add(ti)
  if conf_ec2.Size() > 0:
    confs_ec2.append(conf_ec2)

  Cons.P("%d machine(s)" % len(confs_ec2))
  Cons.P(pprint.pformat(confs_ec2, width=100))
  sys.exit(1)

  for conf_ec2 in confs_ec2:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        , "init_script": "mutant-rocksdb"
        , "ami_name": "mutant-rocksdb"
        , "block_storage_devs": []
        , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
        # Initialize local SSD by erasing. Some EC2 instance types need this.
        , "erase_local_ssd": "true"
        , "unzip_quizup_data": "false"
        , "run_cassandra_server": "false"
        , "rocksdb": {}  # This doesn't do much other than checking out the code and building.
        , "rocksdb-quizup-runs": []
        , "ycsb-runs": []
        , "terminate_inst_when_done": "true"
        }
    if db_stg_dev == "ebs-st1":
      # 40 MiB/s/TiB. With 3 TiB, 120 MiB/sec.
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    elif db_stg_dev == "local-ssd1":
      pass
    else:
      raise RuntimeError("Unexpected")

    ycsb_runs = {
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "workload_type": workload_type
      , "db_path": "/mnt/%s/rocksdb-data/ycsb" % db_stg_dev
      , "db_stg_dev_paths": [
          "/mnt/%s/rocksdb-data/ycsb/t0" % db_stg_dev]
      , "runs": []
      }

    for target_iops in conf_ec2.params:
      op_cnt = 10000000 / 2
      if target_iops < 10000:
        op_cnt = op_cnt / 10
      ycsb_runs["runs"].append({
        # The load phase needs to be slow. Otherwise, the SSTables get too big. Probably because of the pending compactions,
        #   which will affect the performance of in the run phase.
        #   However, with a slow loading like with -target 10000, it takes 16 mins.
        # Decided to keep the DB image in S3. Takes about 1 min to sync.
        "load": {
          #"use_preloaded_db": ""
          # This can be used for any devices. Now the name is misleading, but ok.
          "use_preloaded_db": "ycsb-%s-10M-records-rocksdb" % workload_type
          , "ycsb_params": " -p recordcount=10000000 -target 10000"
          }
        # How long it takes when the system gets saturated.
        #   Without memory throttling, 10M reqs: 101 sec.
        #                              30M reqs: 248 sec
        #   With a 4GB memory throttling, 10M reqs: 119 sec. Not a lot of difference. Hmm.
        #                                 30M reqs: 305 sec. Okay.
        #
        # 11G of data. With 5GB, JVM seems to be doing just fine.
        # Out of the 30M operations, 0.95 of them are reads; 0.05 are writes.
        #   With the raw latency logging, YCSB hogs more memory: it keeps the data in memory.
        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=%s -p readproportion=0.95 -p insertproportion=0.05 -target %d" % (op_cnt, target_iops)
          }
        , "mutant_options": {
          "monitor_temp": "false"
          , "migrate_sstables": "false"
          , "sst_ott": 0
          , "cache_filter_index_at_all_levels": "false"
          # Replaying a workload in the past
          #, "replaying": {
          #  "simulated_time_dur_sec": 1365709.587
          #  , "simulation_time_dur_sec": 60000
          #  }
          , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
          }
        })

    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


# TODO: How are workload d and Zipfian different?
#   what does the workload d do? what portion of the latest records does it read?

def Job_Ycsb_B_Rocksdb():
  # Job conf per EC2 inst
  class ConfEc2Inst:
    exp_per_ec2inst = 7

    def __init__(self):
      self.params = []
    def Full(self):
      return (len(self.params) >= ConfEc2Inst.exp_per_ec2inst)
    def Add(self, params):
      self.params.append(params)
    def Size(self):
      return len(self.params)
    def __repr__(self):
      return "%s" % (self.params)

  #db_stg_dev = "ebs-st1"
  db_stg_dev = "local-ssd1"

  workload_type = "b"

  if db_stg_dev == "local-ssd1":
    target_iops_range = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, \
          10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, \
          100000, 110000, 120000]
  elif db_stg_dev == "ebs-st1":
    target_iops_range = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
  random.shuffle(target_iops_range)

  confs_ec2 = []
  # Target IOPSes
  conf_ec2 = ConfEc2Inst()
  for i in range(5):
    # Target IOPS
    for ti in target_iops_range:
      if conf_ec2.Full():
        confs_ec2.append(conf_ec2)
        conf_ec2 = ConfEc2Inst()
      conf_ec2.Add(ti)
  if conf_ec2.Size() > 0:
    confs_ec2.append(conf_ec2)

  #confs_ec2 = confs_ec2[0:1]
  Cons.P("%d machine(s)" % len(confs_ec2))
  Cons.P(pprint.pformat(confs_ec2, width=100))
  #sys.exit(1)

  for conf_ec2 in confs_ec2:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        , "init_script": "mutant-rocksdb"
        , "ami_name": "mutant-rocksdb"
        , "block_storage_devs": []
        , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
        # Initialize local SSD by erasing. Some EC2 instance types need this.
        , "erase_local_ssd": "true"
        , "unzip_quizup_data": "false"
        , "run_cassandra_server": "false"
        , "rocksdb": {}  # This doesn't do much other than checking out the code and building.
        , "rocksdb-quizup-runs": []
        , "ycsb-runs": []
        , "terminate_inst_when_done": "true"
        }
    if db_stg_dev == "ebs-st1":
      # 40 MiB/s/TiB. With 3 TiB, 120 MiB/sec.
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    elif db_stg_dev == "local-ssd1":
      pass
    else:
      raise RuntimeError("Unexpected")

    ycsb_runs = {
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "workload_type": workload_type
      , "db_path": "/mnt/%s/rocksdb-data/ycsb" % db_stg_dev
      , "db_stg_dev_paths": [
          "/mnt/%s/rocksdb-data/ycsb/t0" % db_stg_dev]
      , "runs": []
      }

    for target_iops in conf_ec2.params:
      ycsb_runs["runs"].append({
        "load": {
          #"use_preloaded_db": ""
          "use_preloaded_db": "ycsb-%s-10M-records-rocksdb" % workload_type
          # For some reason, using the preloaded rocksdb to st1 didn't work. Make a DB snapshot that was loaded on st1.
          #"use_preloaded_db": "ycsb-d-10M-records-rocksdb-st1"
          # Let's try the same one for local ssd. Hope it works. Hope the difference is the separate t0 directory.
          , "ycsb_params": " -p recordcount=10000000 -target 10000"
          # Useful when taking DB snapshots
          , "stop_after_load": "false"
          }
        , "run": {
          "evict_cached_data": "true"
          , "memory_limit_in_mb": 5.0 * 1024
          # Mutant doesn't trigger any of these by default: it behaves like unmodified RocksDB.
          , "ycsb_params": " -p recordcount=10000000 -p operationcount=10000000 -target %d" % target_iops
          }
        , "mutant_options": {
          "monitor_temp": "false"
          , "migrate_sstables": "false"
          , "sst_ott": 0
          , "cache_filter_index_at_all_levels": "false"
          # Replaying a workload in the past
          #, "replaying": {
          #  "simulated_time_dur_sec": 1365709.587
          #  , "simulation_time_dur_sec": 60000
          #  }
          , "db_stg_dev_paths": ycsb_runs["db_stg_dev_paths"]
          }
        })

    params["ycsb-runs"] = dict(ycsb_runs)
    LaunchJob(params)


def Job_RocksBaselineYcsb():
  params = {
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      #, "block_storage_devs": []
      #, "block_storage_devs": [{"VolumeType": "gp2", "VolumeSize": 200, "DeviceName": "d"}]
      #, "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      #, "block_storage_devs": [{"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "erase_local_ssd": "true"
      , "unzip_quizup_data": "false"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "false"
      }

  # Launch 4 instances. The experiment is done manually.
  for bsd in [ \
      []
      , [{"VolumeType": "gp2", "VolumeSize": 200, "DeviceName": "d"}]
      , [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , [{"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"}]
      ]:
    params["block_storage_devs"] = bsd
    LaunchJob(params)


def Job_QuizupMutantSlaAdmin():
  params = {
      #"region": "us-west-2"
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-rocksdb"
      , "ami_name": "mutant-rocksdb"
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "ec2_tag_Name": inspect.currentframe().f_code.co_name[4:]
      , "erase_local_ssd": "true"
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "false"
      }

  qz_run = {
      # Use the current function name since you always forget to set this
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
      , "slow_dev_paths": {"t1": "/mnt/ebs-st1/rocksdb-data-quizup-t1"}
      , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
      , "init_db_to_90p_loaded": "false"
      , "evict_cached_data": "true"
      #, "memory_limit_in_mb": 9.0 * 1024

      # Not caching metadata might be a better idea. So the story is you
      # present each of the optimizations separately, followed by the
      # combined result.
      #, "cache_filter_index_at_all_levels": "false"

      # Cache metadata for a comparison
      , "cache_filter_index_at_all_levels": "true"

      , "monitor_temp": "true"
      , "migrate_sstables": "true"
      #, "sst_ott": 0.0
      , "organize_L0_sstables": "true"
      #, "workload_start_from": 0.899
      #, "workload_stop_at":    0.930
      #, "simulation_time_dur_in_sec": 60000
      , "workload_start_from": -1
      #, "workload_stop_at":    0.2
      # Load 960 secs. Run 3200 sec. About 70 mins total.
      #, "simulation_time_dur_in_sec": 4400

      # 7 times longer running time
      #, "simulation_time_dur_in_sec": 23920
      , "121x_speed_replay": "true"

      # Full experiment. Might be a good one to see how the workload fluctuate.
      #, "workload_stop_at":   -1

      # Target latency, constans of P, I, and D.
      #, "pid_params": "33,1.0,0.0,0.02"

      , "memory_limit_in_mb": 9.0 * 1024

      #, "simulation_time_dur_in_sec": 10800
      #, "workload_stop_at": 0.3
      , "record_size": 10000

      , "sst_ott": 0.0

      # Fast loading phase and SLA admin-enabled run phase.
      #   Load: 17 mins
      #   Run : 50 mins
      #, "simulation_time_dur_in_sec": 7200

      # The latenc is still high even when all sstables are in SSD.. The system is not satured.
      #, "simulation_time_dur_in_sec": 14400

      # The lowest latency with this. Going either way make it higher. 6, 24, 48, 96
      #, "simulation_time_dur_in_sec": 12*3600

      # Back to 6 hours. Increase the read rate by changing the simulation time.
      , "simulation_time_dur_in_sec": 6*3600
      , "workload_stop_at": 0.3

      , "extra_reads": "true"
      #, "xr_queue_size": 1000
      #, "xr_rate": 600

      #, "pid_params": "45,1.0,0.0,0.02"

      , "sla_observed_value_hist_q_size": 10

      #, "error_adj_ranges": "-0.11,-0.035"
      , "xr_queue_size": 10000
      , "xr_gets_per_key": 10

      # Make all SSTables go to EBS st1
      #, "pid_params": "10000.0,1.0,0.0,0.02"

      # Make all SSTables go to LS
      #, "pid_params": "0.000001.0,1.0,0.0,0.02"

      # none, latency, or slow_dev_r_iops
      #, "sla_admin_type": "slow_dev_r_iops"
      , "slow_dev": "xvde"
      #, "slow_dev_target_r_iops": 250

      #, "sst_ott_adj_cooldown_ms": 5000

      # Bigger cooldown time. 5 sec.
      , "sst_ott_adj_cooldown_ms": 5000
      # Wider error margin. +-20%
      , "error_adj_ranges": "-0.2,0.2"
      # "slow_dev_target_r_iops" is not used any more. The first parameter of pid_params is the target_value
      # We don't use I for now. There is already an oscillation without I.
      , "pid_params": "300:1:0:0"
      , "pid_i_exp_decay_factor": 0.9
      }

  # Run for 2 hours
  std_in_min = 2 * 60
  workload_stop_at = 0.00026218181818181818 * (std_in_min - 30) + 0.21348
  qz_run["simulation_time_dur_in_sec"] = std_in_min * 60
  qz_run["workload_stop_at"] = workload_stop_at

  qz_run["xr_gets_per_key"] = 10
  qz_run["xr_iops"] = "50000:100000:200000"

  qz_run["sla_admin_type"] = "slow_dev_r_iops"
  qz_run["pid_params"] = "300:0.5:0.0125:0"
  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  LaunchJob(params)

  # Exploring latency-control
  #qz_run["sla_admin_type"] = "latency"
  #for l in [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75]:
  #  qz_run["pid_params"] = "%d:0.5:0.0125:0" % l
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)

  # Explore I: 0.003125, 0.00625, and 0.0125 look good.
  #for i in [0.003125, 0.00625, 0.0125, 0.025, 0.05, 0.1, 0.2, 0.4]:
  #  qz_run["pid_params"] = "300:0.5:%f:0" % i
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)

  #for i in [25000, 37000, 50000, 62500, 75000, 87500, 100000, 150000, 200000]:
  #  qz_run["xr_iops"] = i
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)

  # Explore D to see if you can get the oscillation.
  #   Anything beyond 0.125 doesn't make much sense. Maybe 0 is what you needed.
  #for d in [1, 2, 4, 8, 16, 32, 64, 128]:
  #for d in [0.25, 0.125]:
  #  qz_run["pid_params"] = "300:1:0:%f" % d
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)

  # By slow_dev_target_r_iops.
  #for sdtri in [25, 50, 75, 100, 150, 400, 450]:
  #  qz_run["slow_dev_target_r_iops"] = sdtri
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)

  # For local SSD, the latency keeps decreasing. Might be from the IO batching.
  # iops_range = [1000.0, 1500.0, 2000.0, 2500.0, 3000.0]:

  # For EBS st1, even 15 (actually 1.5) reads/sec causes a big latency
  #iops_range = [ \
  #          15.0 \
  #    ,     30.0 \
  #    ,     60.0 \
  #    ,    120.0 \
  #    ,    250.0 \
  #    ,    500.0 \
  #    ,   1000.0 \
  #    ,   2000.0 \
  #    ,   4000.0 \
  #    ,   8000.0 \
  #    ]
  #random.shuffle(iops_range)

  # For a mix of LS and EBS st1. Do LS first and see how much load makes sense.
  #   6000, 12000, ..., 1600000
  #iops_range = [ \
  #        25000 \
  #    ,   50000 \
  #    ,  100000 \
  #    ,  200000 \
  #    ,  400000 \
  #    ,  800000 \
  #    , 1600000 \
  #    ]

  #for xr_iops in iops_range:
  #  xr_gets_per_key = 10
  #  qz_run["xr_iops"] = xr_iops
  #  qz_run["xr_gets_per_key"] = xr_gets_per_key
  #  params["rocksdb-quizup-runs"] = [dict(qz_run)]
  #  LaunchJob(params)


def Job_Quizup2LevelMutantStorageUsageBySstMigTempThresholds():
  class Conf:
    exp_per_ec2inst = 1
    def __init__(self, slow_dev):
      self.slow_dev = slow_dev
      self.sst_mig_temp_thrds = []
    def Full(self):
      return (len(self.sst_mig_temp_thrds) >= Conf.exp_per_ec2inst)
    def Add(self, mem_size):
      self.sst_mig_temp_thrds.append(mem_size)
    def Size(self):
      return len(self.sst_mig_temp_thrds)
    def __repr__(self):
      return "(%s, %s)" % (self.slow_dev, self.sst_mig_temp_thrds)

  # [0.25, 256]
  for i in range(-2, 9):
    #Cons.P("%d %f" % (i, math.pow(2, i)))
    mig_temp_thrds = math.pow(2, i)

  num_exp_per_conf = 2
  confs = []
  for slow_dev in ["ebs-gp2"]:
    conf = Conf(slow_dev)
    for j in range(num_exp_per_conf):
      for sst_mig_temp_thrds in [
          0.00390625,  # 2^(-8)
          ]:
#          0.015625,
#          0.0625,
#          0.25,
#          1.0,
#          4.0,
#          16.0,
#          64.0,
#          256.0,
#          1024.0]:  # 2^10
        if conf.Full():
          confs.append(conf)
          conf = Conf(slow_dev)
        conf.Add(sst_mig_temp_thrds)
    if conf.Size() > 0:
      confs.append(conf)

  Cons.P("%d machines" % len(confs))
  Cons.P(pprint.pformat(confs, width=100))
  #sys.exit(1)

  for conf in confs:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        # RocksDB can use the same AMI
        , "init_script": "mutant-cassandra-server-dev"
        , "ami_name": "mutant-cassandra-server"
        , "block_storage_devs": []
        , "unzip_quizup_data": "true"
        , "run_cassandra_server": "false"
        # For now, it doesn't do much other than checking out the code and building.
        , "rocksdb": { }
        , "rocksdb-quizup-runs": []
        , "terminate_inst_when_done": "true"
        }
    if conf.slow_dev == "ebs-gp2":
      # 100GB gp2: 300 baseline IOPS. 2,000 burst IOPS.
      params["block_storage_devs"].append({"VolumeType": "gp2", "VolumeSize": 100, "DeviceName": "d"})
    else:
      raise RuntimeError("Unexpected")

    for mt in conf.sst_mig_temp_thrds:
      p1 = { \
          "exp_desc": inspect.currentframe().f_code.co_name[4:]
          , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
          , "slow_dev_paths": {"t1": "/mnt/%s/rocksdb-data-quizup-t1" % conf.slow_dev}
          , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
          , "init_db_to_90p_loaded": "false"
          , "evict_cached_data": "true"
          # 9GB memory to cache everything in memory.
          , "memory_limit_in_mb": 9.0 * 1024

          , "cache_filter_index_at_all_levels": "true"
          , "monitor_temp": "true"
          , "migrate_sstables": "true"
          , "workload_start_from": -1.0
          , "workload_stop_at":    -1.0
          , "simulation_time_dur_in_sec": 2000
          , "sst_ott": mt
          }
      params["rocksdb-quizup-runs"].append(dict(p1))
    #Cons.P(pprint.pformat(params))
    LaunchJob(params)


def Job_QuizupSstMigTempThresholds_LocalSsd1EbsSt1():
  params = { \
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      , "block_storage_devs": [{"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"}]
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  simulate_full_time_range = True
  simulate_from_90p_time_range = False

  # Full time range experiments. For calculating the storage cost.
  if simulate_full_time_range:
    for sst_mig_temp_thrds in [
        0.00390625,  # 2^(-8)
        0.015625,
        0.0625,
        0.25,
        1.0,
        4.0,
        16.0,
        64.0,
        256.0,
        1024.0]:  # 2^10
      p1 = { \
          # Use the current function name since you always forget to set this
          "exp_desc": inspect.currentframe().f_code.co_name[4:]
          , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
          , "slow_dev_paths": {"t1": "/mnt/local-ssd1/rocksdb-data-quizup/t1"}
          # You don't need to use the slow device for calculating cost
          #, "slow_dev_paths": {"t1": "/mnt/ebs-st1/rocksdb-data-quizup-t1"}
          , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
          , "init_db_to_90p_loaded": "false"
          , "evict_cached_data": "true"
          , "memory_limit_in_mb": 9.0 * 1024

          # This doesn't really matter for measuring the number of compactions
          # and SSTables.
          , "cache_filter_index_at_all_levels": "false"
          , "monitor_temp": "true"
          , "migrate_sstables": "true"
          , "workload_start_from": -1.0
          , "workload_stop_at":    -1.0
          , "simulation_time_dur_in_sec": 2000
          , "sst_ott": sst_mig_temp_thrds
          }
      params["rocksdb-quizup-runs"] = []
      params["rocksdb-quizup-runs"].append(dict(p1))
      Cons.P(pprint.pformat(params))
      #LaunchJob(params)

  # 95% to 100% time range experiments for measuring latency and the number of IOs.
  if simulate_from_90p_time_range:
    class Conf:
      exp_per_ec2inst = 3
      def __init__(self):
        self.sst_mig_temp_thrds = []
      def Full(self):
        return (len(self.sst_mig_temp_thrds) >= Conf.exp_per_ec2inst)
      def Add(self, smtt):
        self.sst_mig_temp_thrds.append(smtt)
      def Size(self):
        return len(self.sst_mig_temp_thrds)
      def __repr__(self):
        return "(%s)" % (self.sst_mig_temp_thrds)

    num_exp_per_conf = 4
    confs = []
    conf = Conf()
    for j in range(num_exp_per_conf):
      # From 2^-10 = 0.0009765625 down to 2^-36
      #for i in range(-10, -38, -2):
      #for i in range(10, -10, -2):
      for sst_mig_temp_thrds in [0.0009765625, 0.0015, 0.0020]:
        if conf.Full():
          confs.append(conf)
          conf = Conf()
        conf.Add(sst_mig_temp_thrds)
    if conf.Size() > 0:
      confs.append(conf)

    Cons.P("%d machines" % len(confs))
    Cons.P(pprint.pformat(confs, width=100))
    sys.exit(1)

    for conf in confs:
      params["rocksdb-quizup-runs"] = []
      for mt in conf.sst_mig_temp_thrds:
        p1 = { \
            # Use the current function name since you always forget to set this
            "exp_desc": inspect.currentframe().f_code.co_name[4:]
            , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
            , "slow_dev_paths": {"t1": "/mnt/ebs-st1/rocksdb-data-quizup-t1"}
            , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
            , "init_db_to_90p_loaded": "true"
            , "evict_cached_data": "true"
            , "memory_limit_in_mb": 2.0 * 1024

            # Not caching metadata might be a better idea. So the story is you
            # present each of the optimizations separately, followed by the
            # combined result.
            #, "cache_filter_index_at_all_levels": "false"

            # Cache metadata for a comparison
            , "cache_filter_index_at_all_levels": "true"

            , "monitor_temp": "true"
            , "migrate_sstables": "true"
            , "workload_start_from": 0.899
            , "workload_stop_at":    -1.0
            , "simulation_time_dur_in_sec": 60000
            , "sst_ott": mt
            }
        params["rocksdb-quizup-runs"].append(dict(p1))
      #Cons.P(pprint.pformat(params))
      LaunchJob(params)


def Job_QuizupLowSstMigTempThresholds_LocalSsd1Only():
  params = { \
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      , "block_storage_devs": []
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }

  # Full time range experiments are for the number of compactions and SSTables.
  # They don't show the number of disk IOs.
  if False:
    # From 2^-10 = 0.0009765625 down to 2^-32
    for i in range(-10, -34, -2):
      sst_mig_temp_thrds = pow(2, i)
      p1 = { \
          # Use the current function name since you always forget to set this
          "exp_desc": inspect.currentframe().f_code.co_name[4:]
          , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
          , "slow_dev_paths": {}
          , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
          , "init_db_to_90p_loaded": "false"
          , "evict_cached_data": "true"
          , "memory_limit_in_mb": 9.0 * 1024

          # This doesn't really matter for measuring the number of compactions
          # and SSTables.
          , "cache_filter_index_at_all_levels": "false"
          , "monitor_temp": "true"
          , "migrate_sstables": "true"
          , "workload_start_from": -1.0
          , "workload_stop_at":    -1.0
          , "simulation_time_dur_in_sec": 20000
          , "sst_ott": sst_mig_temp_thrds
          }
      params["rocksdb-quizup-runs"] = []
      params["rocksdb-quizup-runs"].append(dict(p1))
      #Cons.P(pprint.pformat(params))
      LaunchJob(params)

  # 95% to 100% time range experiments for measuring latency and the number of IOs.
  if True:
    class Conf:
      exp_per_ec2inst = 2
      def __init__(self):
        self.sst_mig_temp_thrds = []
      def Full(self):
        return (len(self.sst_mig_temp_thrds) >= Conf.exp_per_ec2inst)
      def Add(self, smtt):
        self.sst_mig_temp_thrds.append(smtt)
      def Size(self):
        return len(self.sst_mig_temp_thrds)
      def __repr__(self):
        return "(%s)" % (self.sst_mig_temp_thrds)

    num_exp_per_conf = 2
    confs = []
    conf = Conf()
    for j in range(num_exp_per_conf):
      # From 2^-10 = 0.0009765625 down to 2^-32
      for i in range(-10, -34, -2):
        if conf.Full():
          confs.append(conf)
          conf = Conf()
        mig_temp_thrds = math.pow(2, i)
        conf.Add(mig_temp_thrds)
    if conf.Size() > 0:
      confs.append(conf)

    Cons.P("%d machines" % len(confs))
    Cons.P(pprint.pformat(confs, width=100))
    sys.exit(1)

    for conf in confs:
      params["rocksdb-quizup-runs"] = []
      for mt in conf.sst_mig_temp_thrds:
        p1 = { \
            # Use the current function name since you always forget to set this
            "exp_desc": inspect.currentframe().f_code.co_name[4:]
            , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
            , "slow_dev_paths": {}
            , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
            , "init_db_to_90p_loaded": "true"
            , "evict_cached_data": "true"
            , "memory_limit_in_mb": 2.0 * 1024

            # Not caching metadata might be a better idea. So the story is you
            # present each of the optimizations separately, followed by the
            # combined result.
            , "cache_filter_index_at_all_levels": "false"
            , "monitor_temp": "true"
            , "migrate_sstables": "true"
            , "workload_start_from": 0.899
            , "workload_stop_at":    -1.0
            , "simulation_time_dur_in_sec": 60000
            , "sst_ott": mt
            }
        params["rocksdb-quizup-runs"].append(dict(p1))
      #Cons.P(pprint.pformat(params))
      LaunchJob(params)


# TODO: clean up
def Job_QuizupToCleanup2LevelMutantBySstMigTempThresholdsToMeasureStorageUsage():
  class Conf:
    exp_per_ec2inst = 2
    def __init__(self, slow_dev):
      self.slow_dev = slow_dev
      self.sst_mig_temp_thrds = []
    def Full(self):
      return (len(self.sst_mig_temp_thrds) >= Conf.exp_per_ec2inst)
    def Add(self, mem_size):
      self.sst_mig_temp_thrds.append(mem_size)
    def Size(self):
      return len(self.sst_mig_temp_thrds)
    def __repr__(self):
      return "(%s, %s)" % (self.slow_dev, self.sst_mig_temp_thrds)

  # [0.25, 256]
  for i in range(-2, 9):
    #Cons.P("%d %f" % (i, math.pow(2, i)))
    mig_temp_thrds = math.pow(2, i)

  num_exp_per_conf = 2
  confs = []
  if True:
    for slow_dev in ["ebs-gp2"]:
      conf = Conf(slow_dev)
      for j in range(num_exp_per_conf):
        #for i in range(-14, 12, 2):
        for i in range(-20, -14, 2):
          if conf.Full():
            confs.append(conf)
            conf = Conf(slow_dev)
          mig_temp_thrds = math.pow(2, i)
          conf.Add(mig_temp_thrds)
      if conf.Size() > 0:
        confs.append(conf)

  Cons.P("%d machines" % len(confs))
  Cons.P(pprint.pformat(confs, width=100))

  for conf in confs:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        # RocksDB can use the same AMI
        , "init_script": "mutant-cassandra-server-dev"
        , "ami_name": "mutant-cassandra-server"
        , "block_storage_devs": []
        , "unzip_quizup_data": "true"
        , "run_cassandra_server": "false"
        # For now, it doesn't do much other than checking out the code and building.
        , "rocksdb": { }
        , "rocksdb-quizup-runs": []
        , "terminate_inst_when_done": "true"
        }
    if conf.slow_dev == "ebs-gp2":
      # 100GB gp2: 300 baseline IOPS. 2,000 burst IOPS.
      params["block_storage_devs"].append({"VolumeType": "gp2", "VolumeSize": 100, "DeviceName": "d"})
    else:
      raise RuntimeError("Unexpected")

    for mt in conf.sst_mig_temp_thrds:
      p1 = { \
          "exp_desc": inspect.currentframe().f_code.co_name[4:]
          , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
          , "slow_dev_paths": {"t1": "/mnt/%s/rocksdb-data-quizup-t1" % conf.slow_dev}
          , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
          , "init_db_to_90p_loaded": "false"
          , "evict_cached_data": "true"
          , "memory_limit_in_mb": 9.0 * 1024

          , "cache_filter_index_at_all_levels": "true"
          , "monitor_temp": "true"
          , "migrate_sstables": "true"
          , "workload_start_from": -1.0
          , "workload_stop_at":    -1.0
          , "simulation_time_dur_in_sec": 20000
          , "sst_ott": mt
          }
      params["rocksdb-quizup-runs"].append(dict(p1))
    #Cons.P(pprint.pformat(params))
    LaunchJob(params)
  return

  # RocksDB with temperature monitoring and no sstable migration for a comparision
  params = { \
      # us-east-1, which is where the S3 buckets for experiment are.
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      # RocksDB can use the same AMI
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      , "block_storage_devs": []
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }
  p1 = { \
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
      , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
      , "init_db_to_90p_loaded": "false"
      , "evict_cached_data": "true"
      , "memory_limit_in_mb": 9.0 * 1024

      # Doesn't matter. We are interested in the size only.
      , "cache_filter_index_at_all_levels": "false"

      , "monitor_temp": "true"
      , "migrate_sstables": "false"
      , "workload_start_from": -1.0
      , "workload_stop_at":    -1.0
      , "simulation_time_dur_in_sec": 20000
      , "sst_ott": 0
      }
  params["rocksdb-quizup-runs"].append(dict(p1))
  #Cons.P(pprint.pformat(params))
  LaunchJob(params)
  return

  # Unmodified RocksDB too for a comparison
  params = { \
      # us-east-1, which is where the S3 buckets for experiment are.
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      # RocksDB can use the same AMI
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      , "block_storage_devs": []
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }
  p1 = { \
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
      , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
      , "init_db_to_90p_loaded": "false"
      , "evict_cached_data": "true"
      , "memory_limit_in_mb": 9.0 * 1024

      , "cache_filter_index_at_all_levels": "false"
      , "monitor_temp": "false"
      , "migrate_sstables": "false"
      , "workload_start_from": -1.0
      , "workload_stop_at":    -1.0
      , "simulation_time_dur_in_sec": 20000
      , "sst_ott": 0
      }
  params["rocksdb-quizup-runs"].append(dict(p1))
  #Cons.P(pprint.pformat(params))
  LaunchJob(params)


def Job_QuizupUnmodifiedRocksDbWithWithoutMetadataCachingByStgDevs():
  class Conf:
    exp_per_ec2inst = 5
    def __init__(self, stg_dev):
      self.stg_dev = stg_dev
      self.metadata_caching = []
    def Full(self):
      return (len(self.metadata_caching) >= Conf.exp_per_ec2inst)
    def Add(self, metadata_caching):
      self.metadata_caching.append(metadata_caching)
    def Size(self):
      return len(self.metadata_caching)
    def __repr__(self):
      return "(%s, %s)" % (self.stg_dev, self.metadata_caching)

  # The lower bound without getting the system overloaded are different for
  # different storage devices.  local-ssd1 and ebs-gp2 have 14, which is 1.4GB,
  # which the range() function sets the lower bound as 12. They are capped by
  # the main memory. OOM killer.  ebs-st1 can go 1.6GB without the storage
  # device overloaded, ebs-sc1 2.0GB.
  num_exp_per_conf = 4
  confs = []
  for stg_dev in ["local-ssd1", "ebs-gp2", "ebs-st1", "ebs-sc1"]:
    conf = Conf(stg_dev)
    for j in range(num_exp_per_conf):
      for i in ["true", "false"]:
        if conf.Full():
          confs.append(conf)
          conf = Conf(stg_dev)
        conf.Add(i)
    if conf.Size() > 0:
      confs.append(conf)

  Cons.P("%d machines" % len(confs))
  Cons.P(pprint.pformat(confs, width=100))

  for conf in confs:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        # RocksDB can use the same AMI
        , "init_script": "mutant-cassandra-server-dev"
        , "ami_name": "mutant-cassandra-server"
        , "block_storage_devs": []
        , "unzip_quizup_data": "true"
        , "run_cassandra_server": "false"
        # For now, it doesn't do much other than checking out the code and building.
        , "rocksdb": { }
        , "rocksdb-quizup-runs": []
        , "terminate_inst_when_done": "true"
        }
    if conf.stg_dev == "local-ssd1":
      pass
    elif conf.stg_dev == "ebs-gp2":
      params["block_storage_devs"].append({"VolumeType": "gp2", "VolumeSize": 1000, "DeviceName": "d"})
    elif conf.stg_dev == "ebs-st1":
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    elif conf.stg_dev == "ebs-sc1":
      params["block_storage_devs"].append({"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"})
    else:
      raise RuntimeError("Unexpected")

    p1 = { \
        "exp_desc": inspect.currentframe().f_code.co_name[4:]
        , "fast_dev_path": "/mnt/%s/rocksdb-data" % conf.stg_dev
        , "db_path": "/mnt/%s/rocksdb-data/quizup" % conf.stg_dev
        , "init_db_to_90p_loaded": "true"
        , "evict_cached_data": "true"
        , "memory_limit_in_mb": 1024 * 2

        , "cache_filter_index_at_all_levels": None

        , "monitor_temp": "false"
        , "migrate_sstables": "false"
        , "workload_start_from": 0.899
        , "workload_stop_at":    -1.0
        , "simulation_time_dur_in_sec": 60000
        }
    for mc in conf.metadata_caching:
      p1["cache_filter_index_at_all_levels"] = mc
      params["rocksdb-quizup-runs"].append(dict(p1))

    #Cons.P(pprint.pformat(params))
    LaunchJob(params)


def Job_Quizup2LevelMutantLatencyByColdStgBySstMigTempThresholds():
  class Conf:
    exp_per_ec2inst = 7
    def __init__(self, slow_dev):
      self.slow_dev = slow_dev
      self.sst_mig_temp_thrds = []
    def Full(self):
      return (len(self.sst_mig_temp_thrds) >= Conf.exp_per_ec2inst)
    def Add(self, smtt):
      self.sst_mig_temp_thrds.append(smtt)
    def Size(self):
      return len(self.sst_mig_temp_thrds)
    def __repr__(self):
      return "(%s, %s)" % (self.slow_dev, self.sst_mig_temp_thrds)

  # [0.25, 256]
  for i in range(-2, 9):
    #Cons.P("%d %f" % (i, math.pow(2, i)))
    mig_temp_thrds = math.pow(2, i)

  num_exp_per_conf = 4
  confs = []
  # Redo some exps
  if True:
    for slow_dev in ["ebs-gp2", "ebs-st1", "ebs-sc1"]:
      conf = Conf(slow_dev)
      for j in range(num_exp_per_conf):
        #for i in range(-2, 9):
        for i in range(-2, -10, -1):
          if conf.Full():
            confs.append(conf)
            conf = Conf(slow_dev)
          mig_temp_thrds = math.pow(2, i)
          conf.Add(mig_temp_thrds)
      if conf.Size() > 0:
        confs.append(conf)

  if False:
    num_exp_per_conf = 2
    for slow_dev in ["ebs-st1"]:
      conf = Conf(slow_dev)
      for j in range(num_exp_per_conf):
        for i in range(1, 9):
          if conf.Full():
            confs.append(conf)
            conf = Conf(slow_dev)
          mig_temp_thrds = math.pow(2, i)
          conf.Add(mig_temp_thrds)
      if conf.Size() > 0:
        confs.append(conf)

  if False:
    num_exp_per_conf = 4
    for slow_dev in ["ebs-sc1"]:
      conf = Conf(slow_dev)
      for j in range(num_exp_per_conf):
        for i in range(2, 9):
          if conf.Full():
            confs.append(conf)
            conf = Conf(slow_dev)
          mig_temp_thrds = math.pow(2, i)
          conf.Add(mig_temp_thrds)
      if conf.Size() > 0:
        confs.append(conf)

  if False:
    num_exp_per_conf = 4
    for slow_dev in ["ebs-sc1"]:
      conf = Conf(slow_dev)
      for j in range(num_exp_per_conf):
        for i in range(0, 2):
          if conf.Full():
            confs.append(conf)
            conf = Conf(slow_dev)
          mig_temp_thrds = math.pow(2, i)
          conf.Add(mig_temp_thrds)
      if conf.Size() > 0:
        confs.append(conf)

  Cons.P("%d machines" % len(confs))
  Cons.P(pprint.pformat(confs, width=100))
  sys.exit(0)

  for conf in confs:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        # RocksDB can use the same AMI
        , "init_script": "mutant-cassandra-server-dev"
        , "ami_name": "mutant-cassandra-server"
        , "block_storage_devs": []
        , "unzip_quizup_data": "true"
        , "run_cassandra_server": "false"
        # For now, it doesn't do much other than checking out the code and building.
        , "rocksdb": { }
        , "rocksdb-quizup-runs": []
        , "terminate_inst_when_done": "true"
        }
    if conf.slow_dev == "ebs-gp2":
      # 100GB gp2: 300 baseline IOPS. 2,000 burst IOPS.
      params["block_storage_devs"].append({"VolumeType": "gp2", "VolumeSize": 100, "DeviceName": "d"})
    elif conf.slow_dev == "ebs-st1":
      # 1T st1: 40 MiB/s. 250 burst MiB/s. Since most of the requests will be
      # absorbed by local SSD, I think you can go a lot lower than this.
      # Redo some of the experiment with a 3T disk. From SSTable migration temperature threshold 2.
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    elif conf.slow_dev == "ebs-sc1":
      # 1T sc1: 12 MiB/s. 80 burst MiB/s
      # Redo some of the experiment with a 3T disk. From SSTable migration temperature threshold 4.
      params["block_storage_devs"].append({"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"})
    else:
      raise RuntimeError("Unexpected")

    for mt in conf.sst_mig_temp_thrds:
      p1 = { \
          "exp_desc": inspect.currentframe().f_code.co_name[4:]
          , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
          , "slow_dev_paths": {"t1": "/mnt/%s/rocksdb-data-quizup-t1" % conf.slow_dev}
          , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
          , "init_db_to_90p_loaded": "true"
          , "evict_cached_data": "true"
          , "memory_limit_in_mb": 2.0 * 1024

          , "monitor_temp": "true"
          , "workload_start_from": 0.899
          , "workload_stop_at":    -1.0
          , "simulation_time_dur_in_sec": 60000
          , "sst_ott": mt
          }
      params["rocksdb-quizup-runs"].append(dict(p1))
    #Cons.P(pprint.pformat(params))
    LaunchJob(params)


def Job_TestServer():
  params = { \
      # us-east-1, which is where the S3 buckets for experiment are.
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      # RocksDB can use the same AMI
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      , "block_storage_devs": []
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }
  LaunchJob(params)


def Job_QuizupMutantStorageSizeByTime():
  params = { \
      # us-east-1, which is where the S3 buckets for experiment are.
      "region": "us-east-1"
      , "inst_type": "c3.2xlarge"
      , "spot_req_max_price": 1.0
      # RocksDB can use the same AMI
      , "init_script": "mutant-cassandra-server-dev"
      , "ami_name": "mutant-cassandra-server"
      # 100 GB is good enough. 300 baseline IOPS. 2,000 burst IOPS. 3T sc1 has only 36 IOPS.
      , "block_storage_devs": [{"VolumeType": "gp2", "VolumeSize": 100, "DeviceName": "d"}]
      , "unzip_quizup_data": "true"
      , "run_cassandra_server": "false"
      # For now, it doesn't do much other than checking out the code and building.
      , "rocksdb": { }
      , "rocksdb-quizup-runs": []
      , "terminate_inst_when_done": "true"
      }
  p1 = { \
      "exp_desc": inspect.currentframe().f_code.co_name[4:]
      , "fast_dev_path": "/mnt/local-ssd1/rocksdb-data"
      , "slow_dev_paths": {"t1": "/mnt/ebs-gp2/rocksdb-data-quizup-t1"}
      , "db_path": "/mnt/local-ssd1/rocksdb-data/quizup"
      , "init_db_to_90p_loaded": "false"
      , "evict_cached_data": "true"
      , "memory_limit_in_mb": 2.0 * 1024

      , "monitor_temp": "true"
      , "workload_start_from": -1.0
      , "workload_stop_at":    -1.0
      , "simulation_time_dur_in_sec": 60000
      , "sst_ott": 10
      }
  params["rocksdb-quizup-runs"].append(dict(p1))
  LaunchJob(params)


def Job_QuizupUnmodifiedRocksDBLatencyByMemorySizes():
  class Conf:
    exp_per_ec2inst = 8
    def __init__(self, stg_dev):
      self.stg_dev = stg_dev
      self.mem_sizes = []
    def Full(self):
      return (len(self.mem_sizes) >= Conf.exp_per_ec2inst)
    def Add(self, mem_size, force=False):
      if False:
        # Experiment already done
        if not force:
          if ((self.stg_dev == "local-ssd1") and (mem_size in [3.8, 3.6, 3.4, 3.2])) \
              or ((self.stg_dev == "ebs-gp2") and (mem_size in [4.2])):
                return
      self.mem_sizes.append(mem_size)
    def Size(self):
      return len(self.mem_sizes)
    def __repr__(self):
      return "(%s, %s)" % (self.stg_dev, self.mem_sizes)

  # The lower bound without getting the system overloaded are different for
  # different storage devices.  local-ssd1 and ebs-gp2 have 14, which is 1.4GB,
  # which the range() function sets the lower bound as 12. They are capped by
  # the main memory. OOM killer.  ebs-st1 can go 1.6GB without the storage
  # device overloaded, ebs-sc1 2.0GB.
  num_exp_per_conf = 5
  confs = []
  for stg_dev in ["local-ssd1", "ebs-gp2"]:
    conf = Conf(stg_dev)
    for j in range(num_exp_per_conf):
      for i in range(30, 12, -2):
        if conf.Full():
          confs.append(conf)
          conf = Conf(stg_dev)
        conf.Add(i/10.0)
    if conf.Size() > 0:
      confs.append(conf)

  stg_dev = "ebs-st1"
  conf = Conf(stg_dev)
  for j in range(num_exp_per_conf):
    for i in range(30, 14, -2):
      if conf.Full():
        confs.append(conf)
        conf = Conf(stg_dev)
      conf.Add(i/10.0)
  if conf.Size() > 0:
    confs.append(conf)

  stg_dev = "ebs-sc1"
  conf = Conf(stg_dev)
  for j in range(num_exp_per_conf):
    for i in range(30, 18, -2):
      if conf.Full():
        confs.append(conf)
        conf = Conf(stg_dev)
      conf.Add(i/10.0)
  if conf.Size() > 0:
    confs.append(conf)

  # Patch a missed experiment
  #confs[18].mem_sizes = confs[18].mem_sizes[4:]
  #confs = confs[18:19]

  Cons.P("%d machines" % len(confs))
  Cons.P(pprint.pformat(confs, width=100))
  #sys.exit(0)

  for conf in confs:
    params = { \
        # us-east-1, which is where the S3 buckets for experiment are.
        "region": "us-east-1"
        , "inst_type": "c3.2xlarge"
        , "spot_req_max_price": 1.0
        # RocksDB can use the same AMI
        , "init_script": "mutant-cassandra-server-dev"
        , "ami_name": "mutant-cassandra-server"
        , "block_storage_devs": []
        , "unzip_quizup_data": "true"
        , "run_cassandra_server": "false"
        # For now, it doesn't do much other than checking out the code and building.
        , "rocksdb": { }
        , "rocksdb-quizup-runs": []
        , "terminate_inst_when_done": "true"
        }
    if conf.stg_dev == "local-ssd1":
      pass
    elif conf.stg_dev == "ebs-gp2":
      params["block_storage_devs"].append({"VolumeType": "gp2", "VolumeSize": 1000, "DeviceName": "d"})
    elif conf.stg_dev == "ebs-st1":
      params["block_storage_devs"].append({"VolumeType": "st1", "VolumeSize": 3000, "DeviceName": "e"})
    elif conf.stg_dev == "ebs-sc1":
      params["block_storage_devs"].append({"VolumeType": "sc1", "VolumeSize": 3000, "DeviceName": "f"})
    else:
      raise RuntimeError("Unexpected")

    p1 = { \
        "exp_desc": inspect.currentframe().f_code.co_name[4:]
        , "fast_dev_path": "/mnt/%s/rocksdb-data" % conf.stg_dev
        , "db_path": "/mnt/%s/rocksdb-data/quizup" % conf.stg_dev
        , "init_db_to_90p_loaded": "true"
        , "evict_cached_data": "true"
        , "memory_limit_in_mb": 1024 * 3

        , "monitor_temp": "false"
        , "workload_start_from": 0.899
        , "workload_stop_at":    -1.0
        , "simulation_time_dur_in_sec": 60000
        }
    for ms in conf.mem_sizes:
      p1["memory_limit_in_mb"] = 1024.0 * ms
      params["rocksdb-quizup-runs"].append(dict(p1))
    LaunchJob(params)


def LaunchJob(params):
  # Spot instance
  ReqSpotInsts.Req(params)

  # On-demand instance
  #LaunchOnDemandInsts.Launch(params)


if __name__ == "__main__":
  sys.exit(main(sys.argv))
