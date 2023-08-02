#!/bin/bash

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/app/lora-scripts/venv/lib/python3.10/site-packages/tensorrt_libs
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HOME="/app/lora-scripts/huggingface"

controlnet=()

if [[ ${POSE_IMAGE} != "" ]]; then
  controlnet+=(--control_net_models "${CONTROLNET_MODEL}")
  controlnet+=(--guide_image_path "${POSE_IMAGE}")
  controlnet+=(--control_net_weights ${POSE_WEIGHT})

  if [[ ${POSE_PREPROCESS} == 1 ]]; then
    controlnet+=(--control_net_preps canny_63_191)
  else
    controlnet+=(--control_net_preps none)
  fi
fi

python ./sd-scripts/gen_img_diffusers.py \
      --ckpt "${PRETRAINED_MODEL}" \
      --outdir "${OUTPUT_DIR}" \
      --xformers \
      --prompt "${PROMPTS}" \
      --steps ${STEPS} \
      --W ${IMAGE_WIDTH} \
      --H ${IMAGE_HEIGHT} \
      --sampler k_euler_a \
      --network_module networks.lora \
      --network_weights ${MODEL_FILE} \
      --network_mul ${MODEL_WEIGHT} \
      --max_embeddings_multiples 3 \
      --images_per_prompt ${NUM_IMAGES}\
      --seed ${SEED}\
      ${controlnet[@]}
