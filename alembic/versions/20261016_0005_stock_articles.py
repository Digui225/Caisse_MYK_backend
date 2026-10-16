"""Stock : articles distincts des produits, fiches techniques, mouvements par article

`stock_items` (un stock par produit vendu) devient `stock_articles` (ingrédients, boissons,
emballages…) ; `product_components` relie un plat aux articles qu'il consomme. Les lignes de
`stock_items` sont reprises : un article par produit suivi, avec une fiche 1 pour 1.
`products.track_stock` disparaît : un produit est suivi s'il a une fiche technique.

`stock_movements` n'a jamais été alimentée avant ce lot : elle est recréée (la migration
s'arrête si elle contient des lignes, plutôt que de les perdre).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16 12:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_MOVEMENT_TYPES = (
    'PURCHASE_IN', 'SALE_OUT', 'RETURN_IN', 'LOSS_OUT', 'ADJUSTMENT', 'INVENTORY_COUNT'
)
MOVEMENT_TYPES = (*OLD_MOVEMENT_TYPES, 'OPENING')


def _movement_type(values: tuple[str, ...] = MOVEMENT_TYPES) -> sa.Enum:
    return sa.Enum(
        *values, name='stock_movement_type', native_enum=False,
        create_constraint=True, length=32,
    )


def _assert_no_movements() -> None:
    count = op.get_bind().execute(sa.text('SELECT count(*) FROM stock_movements')).scalar_one()
    if count:
        raise RuntimeError(
            f'stock_movements contient {count} ligne(s) : migration interrompue pour ne pas '
            'les perdre. Les reprendre à la main avant de relancer.'
        )


def upgrade() -> None:
    _assert_no_movements()
    op.create_table(
        'stock_articles',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', sa.Enum(
            'PROTEINE', 'BOISSON', 'EPICERIE', 'EMBALLAGE', 'ENTRETIEN', 'ENERGIE',
            name='stock_article_category', native_enum=False, create_constraint=True, length=32,
        ), nullable=False),
        sa.Column('unit', sa.String(length=16), nullable=False),
        sa.Column('out_mode', sa.Enum(
            'RECIPE', 'INVENTORY', name='stock_out_mode', native_enum=False,
            create_constraint=True, length=32,
        ), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('avg_cost_xof', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('alert_threshold', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.CheckConstraint('avg_cost_xof >= 0', name=op.f('ck_stock_articles_avg_cost_positive')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_articles')),
        sa.UniqueConstraint('name', name=op.f('uq_stock_articles_name')),
    )
    op.create_table(
        'product_components',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('article_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('quantity > 0', name=op.f('ck_product_components_quantity_positive')),
        sa.ForeignKeyConstraint(
            ['article_id'], ['stock_articles.id'],
            name=op.f('fk_product_components_article_id_stock_articles'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name=op.f('fk_product_components_product_id_products'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_components')),
        sa.UniqueConstraint(
            'product_id', 'article_id', name='uq_product_components_product_article'
        ),
    )
    op.create_index(op.f('ix_product_components_article_id'), 'product_components',
                    ['article_id'], unique=False)
    op.create_index(op.f('ix_product_components_product_id'), 'product_components',
                    ['product_id'], unique=False)

    # reprise : l'identifiant de stock_items devient celui de l'article
    op.execute("""
        INSERT INTO stock_articles (id, name, category, unit, out_mode, quantity, avg_cost_xof,
                                    alert_threshold, is_active)
        SELECT s.id, p.name, 'BOISSON', s.unit, 'RECIPE', s.quantity, 0, s.alert_threshold, true
        FROM stock_items s JOIN products p ON p.id = s.product_id
    """)
    op.execute("""
        INSERT INTO product_components (id, product_id, article_id, quantity)
        SELECT gen_random_uuid(), s.product_id, s.id, 1 FROM stock_items s
    """)
    op.drop_table('stock_items')
    op.drop_column('products', 'track_stock')

    op.drop_index(op.f('ix_stock_movements_product_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.create_table(
        'stock_movements',
        sa.Column('article_id', sa.Uuid(), nullable=False),
        sa.Column('type', _movement_type(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('quantity_after', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit_cost_xof', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('reference_order_id', sa.Uuid(), nullable=True),
        sa.Column('reference_order_item_id', sa.Uuid(), nullable=True),
        sa.Column('supplier', sa.String(length=120), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(
            ['article_id'], ['stock_articles.id'],
            name=op.f('fk_stock_movements_article_id_stock_articles'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['reference_order_id'], ['orders.id'],
            name=op.f('fk_stock_movements_reference_order_id_orders'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['reference_order_item_id'], ['order_items.id'],
            name=op.f('fk_stock_movements_reference_order_item_id_order_items'),
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name=op.f('fk_stock_movements_user_id_users'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_movements')),
    )
    op.create_index(op.f('ix_stock_movements_article_id'), 'stock_movements', ['article_id'],
                    unique=False)
    op.create_index(op.f('ix_stock_movements_business_date'), 'stock_movements',
                    ['business_date'], unique=False)
    op.create_index(op.f('ix_stock_movements_reference_order_id'), 'stock_movements',
                    ['reference_order_id'], unique=False)
    # quantité = somme des mouvements : la quantité reprise devient un stock de départ
    op.execute("""
        INSERT INTO stock_movements (id, article_id, type, quantity, quantity_after,
                                     unit_cost_xof, business_date, reason)
        SELECT gen_random_uuid(), id, 'OPENING', quantity, quantity, avg_cost_xof, current_date,
               'Reprise de stock_items (migration 0005)'
        FROM stock_articles WHERE quantity <> 0
    """)


def downgrade() -> None:
    # le journal des mouvements par article n'a pas d'équivalent par produit : il est perdu
    op.drop_index(op.f('ix_stock_movements_reference_order_id'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_business_date'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_article_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.create_table(
        'stock_movements',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('type', _movement_type(OLD_MOVEMENT_TYPES), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('quantity_after', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit_cost_xof', sa.Integer(), nullable=True),
        sa.Column('reference_order_id', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'],
                                name=op.f('fk_stock_movements_product_id_products'),
                                ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reference_order_id'], ['orders.id'],
                                name=op.f('fk_stock_movements_reference_order_id_orders'),
                                ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name=op.f('fk_stock_movements_user_id_users'),
                                ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_movements')),
    )
    op.create_index(op.f('ix_stock_movements_product_id'), 'stock_movements', ['product_id'],
                    unique=False)

    op.add_column('products', sa.Column('track_stock', sa.Boolean(), server_default=sa.false(),
                                        nullable=False))
    op.create_table(
        'stock_items',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit', sa.String(length=16), nullable=False),
        sa.Column('alert_threshold', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'],
                                name=op.f('fk_stock_items_product_id_products'),
                                ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_items')),
        sa.UniqueConstraint('product_id', name=op.f('uq_stock_items_product_id')),
    )
    # seules les fiches « 1 article, quantité 1 » (boissons) ont un équivalent par produit
    op.execute("""
        INSERT INTO stock_items (id, product_id, quantity, unit, alert_threshold)
        SELECT gen_random_uuid(), c.product_id, a.quantity, a.unit, a.alert_threshold
        FROM product_components c JOIN stock_articles a ON a.id = c.article_id
        WHERE c.quantity = 1
          AND c.product_id IN (SELECT product_id FROM product_components
                               GROUP BY product_id HAVING count(*) = 1)
    """)
    op.execute("""
        UPDATE products SET track_stock = true
        WHERE id IN (SELECT DISTINCT product_id FROM product_components)
    """)
    op.drop_index(op.f('ix_product_components_product_id'), table_name='product_components')
    op.drop_index(op.f('ix_product_components_article_id'), table_name='product_components')
    op.drop_table('product_components')
    op.drop_table('stock_articles')
