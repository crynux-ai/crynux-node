prefix = /usr/local
all: linux_binary

clean:
	rm -rf ./build/crynux_node
	rm -rf ./src/webui/dist
	rm -rf ./src/webui/node_modules


linux_binary:
	./build/linux-server/build.sh

install: linux_binary
	install -D ./build/crynux_node/dist/crynux-node-helium-v2.0.6-linux-x64 \
		$(DESTDIR)$(prefix)/crynux-node

uninstall:
	rm -rf $(DESTDIR)$(prefix)/crynux-node
