curl -L https://github.com/crynux-ai/crynux-node/releases/download/v2.0.1/crynux-node-helium-v2.0.1-mac-apple-silicon.dmg --output Crynux.dmg

# Unsigned app need to be explicitly handled with.
sudo xattr -ds com.apple.quarantine Crynux.dmg
open Crynux.dmg