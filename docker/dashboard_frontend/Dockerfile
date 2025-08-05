FROM node:24

WORKDIR /app

COPY ./zeebra-dashboard /app
COPY ./docker/dashboard_frontend /app/docker

RUN apt update
RUN npm install -g bun
RUN npm install pm2 -g

RUN npm install
RUN bun install

RUN chmod +x ./docker/init.sh
ENTRYPOINT ["./docker/init.sh"]