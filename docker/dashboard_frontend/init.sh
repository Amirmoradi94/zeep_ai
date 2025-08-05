#!/bin/sh

npm run build

pm2-runtime start npm --name "dashboard_frontend" -- run preview