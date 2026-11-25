# Include in the Oregon edge's existing /assets/ origin location.
# LibreChat sets s-maxage on static files and no-store on the HTML fallback.
proxy_buffering on;
proxy_cache pico_assets;
proxy_cache_key "$host$request_uri";
proxy_cache_use_stale updating error timeout http_502 http_504;
proxy_cache_background_update on;
proxy_cache_revalidate on;

# A cold fill took 21s during #1419. Coalesce concurrent requests for that file.
proxy_cache_lock on;
proxy_cache_lock_age 30s;
proxy_cache_lock_timeout 30s;
