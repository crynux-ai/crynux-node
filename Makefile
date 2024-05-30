prefix = /usr/local
all: linux_binary

linux_binary:
	./build/linux-server/build.sh

install: linux_binary
	install -D ./build/crynux_node/dist/crynux-node-helium-v2.0.6-linux-x64 \
		$(DESTDIR)$(prefix)/crynux-node-helium-v2.0.6-linux-x64
