.PHONY: all clean lint test
LIBPOKEREADER := reader_core/target/armv6k-nintendo-3ds/release/libpokereader.a

R_SRCS := $(shell find reader_core/src -name '*.rs')
C_SRCS := $(shell find 3gx/sources -name '*.c')
H_SRCS := $(shell find 3gx/includes -name '*.h')

all: out/default.3gx

$(LIBPOKEREADER): $(R_SRCS)
	cargo +nightly-2024-03-21 build --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

out/default.3gx: $(LIBPOKEREADER) $(C_SRCS) $(H_SRCS)
	# v12 phase-fit validation build: no memory-window probe. Keep only the
	# lightweight existing sample path, retain 48 pre-trigger rows, and bump CSV.
	sed -i 's/#define F604_CANDIDATE_ADDR 0x0022F604u/#define F604_CANDIDATE_ADDR 0x0021B608u/' 3gx/sources/blue_dvtrace.c
	sed -i 's/trigger_seq > 8u ? trigger_seq - 8u : 1u/trigger_seq > 48u ? trigger_seq - 48u : 1u/' 3gx/sources/blue_dvtrace.c
	sed -i 's/phase_probe_begin(trigger_entry.div);/phase_probe_reset();/' 3gx/sources/blue_dvtrace.c
	sed -i 's/"MEWTWO,9,/"MEWTWO,12,/' 3gx/sources/blue_dvtrace.c
	make clean -C 3gx
	make -C 3gx
	mkdir -p out
	cp 3gx/build/3gx.3gx out/default.3gx

clean:
	cargo clean --manifest-path reader_core/Cargo.toml
	make clean -C 3gx
	rm -rf out

format:
	cargo +nightly fmt --all --manifest-path reader_core/Cargo.toml

lint:
	cargo +nightly-2024-03-21 clippy --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

test:
	cargo +nightly-2024-03-21 test --manifest-path reader_core/Cargo.toml
