.PHONY: all clean lint test prepare
LIBPOKEREADER := reader_core/target/armv6k-nintendo-3ds/release/libpokereader.a
PHASE_PREP := prepare_blue_divphase_v12.sh

R_SRCS := $(shell find reader_core/src -name '*.rs')
C_SRCS := $(shell find 3gx/sources -name '*.c')
H_SRCS := $(shell find 3gx/includes -name '*.h')

all: out/default.3gx

prepare:
	sh $(PHASE_PREP)

$(LIBPOKEREADER): prepare $(R_SRCS)
	cargo +nightly-2024-03-21 build --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

out/default.3gx: prepare $(LIBPOKEREADER) $(C_SRCS) $(H_SRCS)
	make clean -C 3gx
	make -C 3gx
	mkdir -p out
	cp 3gx/build/3gx.3gx out/default.3gx

clean:
	cargo clean --manifest-path reader_core/Cargo.toml
	make clean -C 3gx
	rm -rf out

format: prepare
	cargo +nightly fmt --all --manifest-path reader_core/Cargo.toml

lint: prepare
	cargo +nightly-2024-03-21 clippy --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

test: prepare
	cargo +nightly-2024-03-21 test --manifest-path reader_core/Cargo.toml
