local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  description: 'Save Patreon content you have access to.',
  keywords: ['command line', 'patreon'],
  project_name: 'patreon-archiver',
  version: '0.1.6',
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
          requests: utils.latestPypiPackageVersionCaret('requests'),
          'yt-dlp-utils': utils.latestPypiPackageVersionCaret('yt-dlp-utils'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-requests': utils.latestPypiPackageVersionCaret('types-requests'),
              'types-yt-dlp': utils.latestPypiPackageVersionCaret('types-yt-dlp'),
            },
          },
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
