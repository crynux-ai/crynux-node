# Example call: bash app.sh ~/crynux_data
source venv/bin/activate
pyinstaller crynux.spec

source worker/venv/bin/activate
# change in controlnet_aux/zoe/zoedepth/models/layers/attractor.py
TAR_FILE=worker/venv/lib/python3.10/site-packages/controlnet_aux/zoe/zoedepth/models/layers/attractor.py
sed -i.bak "s/@torch.jit.script/#@torch.jit.script/g" $TAR_FILE
pyinstaller crynux_worker_proc.spec

DATA_DIR=$1
RES_DIR=dist/Crynux.app/Contents/Resources

cp -R webui "$RES_DIR/"
mv dist/crynux_worker_proc_main dist/Crynux.app/Contents/MacOS/

if [ $DATA_DIR ] && [ -d $DATA_DIR ]; then
    echo "$DATA_DIR exist, copy it to macapp"
    mkdir "$RES_DIR/data"
    cp -R  $DATA_DIR/* "$RES_DIR/data/"
else
  # In case the data has been stored elsewhere
  mkdir "$RES_DIR/data"
  mkdir "$RES_DIR/data/external"
  mkdir "$RES_DIR/data/huggingface"
  mkdir "$RES_DIR/data/results"
  mkdir "$RES_DIR/data/inference-logs"
fi

cd dist
sudo xattr -rds com.apple.quarantine Crynux.app
[ -e Crynux.dmg ] && rm Crynux.dmg
create-dmg \
    --volname "Crynux" --volicon "../res/icon.icns" \
    --window-pos 200 120 --window-size 800 400 --icon-size 100 \
    --icon "Crynux.app" 200 190 --hide-extension "Crynux.app" \
    --app-drop-link 600 185 \
    "Crynux.dmg" "Crynux.app"
sudo xattr -rds com.apple.quarantine Crynux.dmg
open .