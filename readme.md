# Guid

1. Build keeper-bot image
```
docker build keeper-bot -t keeper-bot
```
2. Start bot in container:
```
docker run -e MONGO_URL=<MONGO_URL> -e TG_TOKEN=<TG_TOKEN> keeper-bot
```

