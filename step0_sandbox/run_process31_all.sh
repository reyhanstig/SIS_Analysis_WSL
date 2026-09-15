#!/bin/bash
cd /home/reyha/SIS_Analysis_WSL/step5_environmental_factor_correlation_analysis

regions=("Seto Inland Sea" "Tokyo Bay" "Ise Bay")
seasons=("Spring" "Summer" "Autumn" "Winter")
layers=("surface" "bottom")
data_types=("env" "nutr")

for r in "${regions[@]}"; do
  for s in "${seasons[@]}"; do
    for l in "${layers[@]}"; do
      for d in "${data_types[@]}"; do
        echo "Running process31 for $r | $s | $l | $d"
        conda run -n sis_analysis env PYTHONPATH=/home/reyha/SIS_Analysis_WSL python process31_correlation_distribution.py \
          --target_region "$r" \
          --season "$s" \
          --layer "$l" \
          --data_type "$d"
      done
    done
  done
done
