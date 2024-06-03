prefix = /usr/local
all: linux_binary

clean:
	rm -rf ./build
	rm -rf ./dist

linux_binary:
	./package.sh

install: linux_binary
	install -D ./dist/crynux-node-helium-v2.0.6-linux-x64 \
		$(DESTDIR)$(prefix)/crynux-node

uninstall:
	rm -rf $(DESTDIR)$(prefix)/crynux-node
