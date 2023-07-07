#!/bin/bash

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/app/lora-scripts/venv/lib/python3.10/site-packages/tensorrt_libs

python ./sd-scripts/gen_img_diffusers.py \
      --ckpt ${PRETRAINED_MODEL} \
      --outdir ${OUTPUT_DIR} \
      --xformers \
      --prompt "${PROMPT}" \
      --steps ${STEPS} \
      --W 768 \
      --H 1024 \
      --sampler k_euler_a \
      --network_module networks.lora \
      --network_weights ${MODEL_FILE} \
      --network_mul ${MODEL_WEIGHT}
