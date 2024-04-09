curl -L ...
MACAPP_CHECKSUM=""

if [[ -n $(shasum crynux.dmg | grep $MACAPP_CHECKSUM) ]]; then
    # Unsigned app need to be explicitly handled with.
    sudo xattr -rds com.apple.quarantine crynux.dmg
    open Crynux.dmg
fi