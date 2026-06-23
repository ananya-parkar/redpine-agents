Agent 2 PostgreSQL Setup
 
## Create database: 
docker exec -it redpine-postgres psql -U postgres -c "CREATE DATABASE stadium_leads;"
 
## Copy schema:
docker cp schema.sql redpine-postgres:/schema.sql
 
## Execute schema: 
docker exec -it redpine-postgres psql -U postgres -d stadium_leads -f /schema.sql
 