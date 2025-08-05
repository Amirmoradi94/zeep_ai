#!/bin/sh

npm run build

pm2-runtime start npm --name "website" -- run preview