FROM nginx:1.27-alpine

# Remove default nginx content
RUN rm -rf /usr/share/nginx/html/*

# Copy shell web files
COPY index.html /usr/share/nginx/html/
COPY style.css  /usr/share/nginx/html/
COPY app.js     /usr/share/nginx/html/
COPY api.js     /usr/share/nginx/html/
COPY llm.js     /usr/share/nginx/html/
COPY renderer.js /usr/share/nginx/html/

# Custom nginx config for SPA
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Cache static assets
    location ~* \.(css|js)$ {
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Health check
    location /healthz {
        access_log off;
        return 200 "ok";
        add_header Content-Type text/plain;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
