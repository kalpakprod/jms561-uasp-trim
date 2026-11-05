.DEFAULT_GOAL := test
.PHONY: test vendor

vendor: ## download Ugreen's 2018 firmware package from its public mirror and check its sha256
	tools/fetch-ugreen-2018

test: vendor ## offline checks: CRC, builder, patch in an 8051 simulator, flashing wrapper, TRIM test logic
	python3 -m unittest discover -s tests -t . -v
	cargo test --offline --manifest-path tools/jms561u-usb/Cargo.toml
