local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  description: 'Save Patreon content you have access to.',
  keywords: ['command line', 'patreon'],
  project_name: 'patreon-archiver',
  version: '0.2.0',
  want_main: true,
  want_flatpak: true,
  publishing+: { flathub: 'sh.tat.patreon-archiver' },
  security_policy_supported_versions: { '0.1.x': ':white_check_mark:' },
  pyproject+: {
    project+: {
      scripts: {
        'patreon-archiver': 'patreon_archiver.main:main',
      },
    },
    tool+: {
      poetry+: {
        dependencies+: {
          anyio: utils.latestPypiPackageVersionCaret('anyio'),
          niquests: utils.latestPypiPackageVersionCaret('niquests'),
          'yt-dlp-utils': {
            extras: ['asyncio'],
            version: utils.latestPypiPackageVersionCaret('yt-dlp-utils'),
          },
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-yt-dlp': utils.latestPypiPackageVersionCaret('types-yt-dlp'),
            },
          },
          tests+: {
            dependencies+: {
              'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
            },
          },
        },
      },
      pytest+: {
        ini_options+: {
          asyncio_default_fixture_loop_scope: 'function',
          asyncio_mode: 'auto',
        },
      },
      uv+: {
        'exclude-newer-package'+: {
          'yt-dlp-utils': false,
        },
      },
    },
  },
  readthedocs+: {
    sphinx+: {
      fail_on_warning: false,
    },
  },
}
