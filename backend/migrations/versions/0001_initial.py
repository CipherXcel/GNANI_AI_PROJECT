"""Initial audio notes schema, durable jobs, and worker heartbeat."""
from alembic import op
from app.database import Base
from app import models

revision = "0001"
down_revision = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
