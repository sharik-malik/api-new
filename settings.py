import os
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'postgres://adres_user:KrZNEKjlTM9@db:5432/adres_database')
    )
}
