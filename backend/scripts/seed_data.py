"""Seed script for development data.

Creates:
- Default organization "AnnexOps Dev"
- Admin user "admin@annexops.local" (password provided via env)

Can be run multiple times safely (skips if exists).
"""
import os
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

    org_name = os.environ.get("SEED_ORG_NAME", "AnnexOps Dev")
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@annexops.local")
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not admin_password:
        print("✗ Missing SEED_ADMIN_PASSWORD environment variable")
        print("  Example: SEED_ADMIN_PASSWORD='YourStrongPassword123!' python scripts/seed_data.py")
        return

    # Get database session
    async for db in get_db():
        # Check if organization already exists
        result = await db.execute(
            select(Organization).where(Organization.name == org_name)
        )
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print(f"✓ Organization '{org_name}' already exists (ID: {existing_org.id})")
            org = existing_org
        else:
            # Create default organization
            org = Organization(
                name=org_name,
                is_active=True
            )
            db.add(org)
            await db.flush()  # Get org.id for user creation
            print(f"✓ Created organization '{org_name}' (ID: {org.id})")

        # Check if admin user already exists
        result = await db.execute(
            select(User).where(User.email == admin_email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"✓ Admin user '{admin_email}' already exists (ID: {existing_user.id})")
        else:
            # Validate password
            try:
                validate_password(admin_password)
            except PasswordValidationError as e:
                print(f"✗ Password validation failed: {e}")
                return

            # Create admin user
            user = User(
                org_id=org.id,
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(user)
            print(f"✓ Created admin user '{admin_email}'")

        # Commit changes
        await db.commit()

    print("\n✓ Database seeding completed successfully!")
    print("\nYou can now login with:")
    print(f"  Email: {admin_email}")


if __name__ == "__main__":
    asyncio.run(seed_data())
