local utils = import 'utils.libjsonnet';

{
  description: 'Save Patreon content you have access to.',
  keywords: ['command line', 'patreon'],
  project_name: 'patreon-archiver',
  version: '0.1.5',
  want_main: true,
  supported_python_versions: ['3.%d' % i for i in std.range(12, 13)],
  copilot: {
    intro: 'Patreon Archiver is a command line tool to save content from Patreon that you have access to.',
  },
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
