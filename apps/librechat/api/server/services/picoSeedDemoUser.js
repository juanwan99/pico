/**
 * Pico: optional demo user seed for VPS / empty Mongo.
 * Enable explicitly with PICO_DEMO_SEED=1.
 * Never logs the password.
 */
const bcrypt = require('bcryptjs');
const { logger } = require('@librechat/data-schemas');
const { isEnabled } = require('@librechat/api');
const { findUser, updateUser } = require('~/models');
const { registerUser } = require('~/server/services/AuthService');

async function seedPicoDemoUser() {
  if (process.env.PICO_DEMO_SEED !== '1') {
    return;
  }

  const email = (process.env.PICO_DEMO_EMAIL || '').trim().toLowerCase();
  const password = process.env.PICO_DEMO_PASSWORD || '';
  if (!email || password.length < 12) {
    logger.error(
      '[picoSeedDemoUser] PICO_DEMO_EMAIL and a 12+ character password are required',
    );
    return;
  }
  const name = process.env.PICO_DEMO_NAME || 'Pico Teacher';
  const username = process.env.PICO_DEMO_USERNAME || 'teacher';
  const forcePassword = isEnabled(process.env.PICO_SEED_DEMO_RESET_PASSWORD);

  try {
    const existing = await findUser({ email }, '+password email emailVerified username');
    if (!existing) {
      const result = await registerUser(
        {
          email,
          password,
          name,
          username,
          confirm_password: password,
        },
        { emailVerified: true },
      );
      logger.info(`[picoSeedDemoUser] register status=${result?.status} email=${email}`);
      // registerUser may return 200 even when email in use after race; re-check
      const created = await findUser({ email }, 'email emailVerified');
      if (created && !created.emailVerified) {
        await updateUser(created._id, { emailVerified: true });
      }
      return;
    }

    const patch = {};
    if (!existing.emailVerified) {
      patch.emailVerified = true;
    }
    if (forcePassword) {
      const salt = bcrypt.genSaltSync(10);
      patch.password = bcrypt.hashSync(password, salt);
    }
    if (Object.keys(patch).length) {
      await updateUser(existing._id, patch);
      logger.info(
        `[picoSeedDemoUser] updated existing email=${email} fields=${Object.keys(patch).join(',')}`,
      );
    } else {
      logger.info(`[picoSeedDemoUser] demo user already ok email=${email}`);
    }
  } catch (err) {
    // Non-fatal: login can still be fixed via scripts/vps-seed-demo-user.sh
    logger.error('[picoSeedDemoUser] failed (non-fatal):', err);
  }
}

module.exports = { seedPicoDemoUser };
