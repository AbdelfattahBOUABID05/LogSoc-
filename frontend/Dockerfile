# Stage 1: Build the Angular app
FROM node:18-alpine AS build
WORKDIR /app

# Copier les fichiers de dépendances pour profiter du cache Docker
COPY package*.json ./
RUN npm install

# Copier le reste des fichiers et builder l'application
COPY . .
RUN npm run build -- --configuration production --subresource-integrity --output-hashing=all

# Stage 2: Serve using nginx
FROM nginx:stable-alpine
# Copier la configuration personnalisée de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copier les fichiers buildés depuis le stage précédent
# L'emplacement dépend de 'outputPath' dans angular.json
COPY --from=build /app/dist/loganalyzer-frontend /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
