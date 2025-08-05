FROM node:24

WORKDIR /app

COPY ./zeebra-website /app
COPY ./docker/website /app/docker

RUN apt update
RUN npm install -g bun
RUN npm install pm2 -g

RUN npm install
RUN bun install

RUN chmod +x ./docker/init.sh
ENTRYPOINT ["./docker/init.sh"]