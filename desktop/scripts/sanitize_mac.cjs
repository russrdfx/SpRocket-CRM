// Remove Finder metadata from generated build files before signing.
// Quarantine and other security attributes are deliberately preserved.
const {execFileSync} = require('node:child_process');
const path = require('node:path');
module.exports = async context => {
  if (context.electronPlatformName !== 'darwin') return;
  const bundle = path.join(context.appOutDir, 'SpRocket CRM.app');
  for (const attribute of ['com.apple.FinderInfo', 'com.apple.ResourceFork']) {
    execFileSync('/usr/bin/xattr', ['-dr', attribute, bundle], {stdio: 'pipe'});
  }
};
