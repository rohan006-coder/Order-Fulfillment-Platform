from alembic import op
import sqlalchemy as sa
from app.db import Base
from app.models.entities import *

revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    # The SQLAlchemy metadata is intentionally imported so this migration remains
    # easy to regenerate/extend. For the take-home, create_all is used by tests;
    # production deployments should run a generated Alembic revision.
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    bind=op.get_bind()
    Base.metadata.drop_all(bind=bind)

