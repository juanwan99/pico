# Include in the Oregon edge's existing /assets/ origin location.
# LibreChat sets s-maxage on static files and no-store on the HTML fallback.
proxy_buffering on;
proxy_cache pico_assets;
proxy_cache_key "$host$request_uri";

# A cold fill took 21s during #1419. Coalesce concurrent requests for that file.
proxy_cache_lock on;
proxy_cache_lock_age 30s;
proxy_cache_lock_timeout 30s;
