FROM nginx
# COPY --from=build /app/frontend/build /usr/share/nginx/html

# COPY static-html-directory /usr/share/nginx/html

RUN apt update
RUN apt-get install apache2-utils -y

# Install ping and net-tools
RUN apt install inetutils-ping -y
RUN apt install net-tools -y

CMD [ "nginx","-g","daemon off;"]