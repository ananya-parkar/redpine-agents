Agent 1 PostgreSQL Setup
 
## Create database:
 
docker exec -it redpine-postgres psql -U postgres -c "CREATE DATABASE redpine;"
 
## Copy schema:
 
docker cp schema.sql redpine-postgres:/schema.sql
 
## Execute schema:
 
docker exec -it redpine-postgres psql -U postgres -d redpine -f /schema.sql
 