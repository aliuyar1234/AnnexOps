"""Seed script for development data.

Creates:
- Default organization "AnnexOps Dev"
- Admin user "admin@annexops.local" with password "Admin123!"

Can be run multiple times safely (skips if exists).
"""
import sys
from pathlib import Path
import asyncio

# Add backend/src to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from src.core.database import get_db
from src.models.organization import Organization
from src.models.user import User
from src.models.enums import UserRole
from src.core.security import hash_password, validate_password, PasswordValidationError


async def seed_data():
    """Seed development data."""
    print("Starting database seeding...")

    # Get database session
    async for db in get_db():
        # Check if organization already exists
        result = await db.execute(
            select(Organization).where(Organization.name == "AnnexOps Dev")
        )
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print(f"✓ Organization 'AnnexOps Dev' already exists (ID: {existing_org.id})")
            org = existing_org
        else:
            # Create default organization
            org = Organization(
                name="AnnexOps Dev",
                is_active=True
            )
            db.add(org)
            await db.flush()  # Get org.id for user creation
            print(f"✓ Created organization 'AnnexOps Dev' (ID: {org.id})")

        # Check if admin user already exists
        result = await db.execute(
            select(User).where(User.email == "admin@annexops.local")
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"✓ Admin user 'admin@annexops.local' already exists (ID: {existing_user.id})")
        else:
            # Validate password
            password = "Admin123!"
            try:
                validate_password(password)
            except PasswordValidationError as e:
                print(f"✗ Password validation failed: {e}")
                return

            # Create admin user
            user = User(
                email="admin@annexops.local",
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                organization_id=org.id,
                is_active=True
            )
            db.add(user)
            print(f"✓ Created admin user 'admin@annexops.local'")
            print(f"  Password: {password}")

        # Commit changes
        await db.commit()

    print("\n✓ Database seeding completed successfully!")
    print("\nYou can now login with:")
    print("  Email: admin@annexops.local")
    print("  Password: Admin123!")


if __name__ == "__main__":
    asyncio.run(seed_data())
