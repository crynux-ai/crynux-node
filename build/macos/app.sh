# Example call: bash app.sh ~/crynux_data
source /venv/bin/activate
pyinstaller crynux.spec

DATA_DIR=$1
RES_DIR=dist/Crynux.app/Contents/Resources

cp -R worker "$RES_DIR/"
cp -R webui "$RES_DIR/"

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
[ -e crynux.dmg ] && rm crynux.dmg
create-dmg \
    --volname "crynux" --volicon "../res/icon.icns" \
    --window-pos 200 120 --window-size 800 400 --icon-size 100 \
    --icon "crynux.app" 200 190 --hide-extension "crynux.app" \
    --app-drop-link 600 185 \
    "crynux.dmg" "crynux.app"
