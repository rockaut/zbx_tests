docker run --rm -ti -e CGO_LDFLAGS_ALLOW=".*\.*" -v "$PWD":/go/src -w /go/src golang:1.10 make clean
docker run --rm -ti -e CGO_LDFLAGS_ALLOW=".*\.*" -v "$PWD":/go/src -w /go/src golang:1.10 make