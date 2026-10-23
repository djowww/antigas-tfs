FROM ubuntu:22.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake pkg-config libboost-system-dev libboost-filesystem-dev libluajit-5.1-dev libpugixml-dev libmariadb-dev libmariadb-dev-compat libgmp-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt ./
COPY src/ src/
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel 2
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends libboost-system1.74.0 libboost-filesystem1.74.0 libluajit-5.1-2 libpugixml1v5 libmariadb3 libgmp10 python3 python3-cryptography && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/server
COPY --from=build /src/build/tfs ./tfs
COPY data/ data/
COPY local/config.lua ./config.lua
COPY local/entrypoint.py /entrypoint.py
ENTRYPOINT ["python3", "/entrypoint.py"]
