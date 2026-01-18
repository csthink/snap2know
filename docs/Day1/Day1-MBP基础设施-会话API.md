# Day 1：MBP 基础设施 + 会话 API

## Qdrant 向量数据库

[Qdrant 安装指南](https://qdrant.tech/documentation/quickstart/)

- 在 MBP 上使用Docker安装qdrant

```shell
docker pull qdrant/qdrant

mkdir -p ~/dc/devops/docker/qdrant_storage

docker run -idt \
  -p 6333:6333 \
  -v ~/dc/devops/docker/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

[Web UI](http://localhost:6333/dashboard)

![Qdrant Web UI](./images/qdrant_1.png)


```shell
curl http://localhost:6333/healthz
```

![Qdrant Health Check From CLI](./images/qdrant_2.png)

![Qdrant Health Check From Web UI](./images/qdrant_3.png)
