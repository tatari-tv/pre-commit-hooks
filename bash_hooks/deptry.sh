#!/usr/bin/env bash

output=$(poetry run deptry . 2>&1)
status=$?

if [ $status -ne 0 ]; then
    echo "$output"
    exit $status
fi
