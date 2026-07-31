FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3009
# dev server (uso local do casal); para produção, trocar por build + serve estático
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3009"]
