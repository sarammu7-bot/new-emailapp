pipeline {
    agent any

    environment {
        // Git
        GIT_CREDS  = 'github-token-emailapp'
        GIT_REPO   = 'https://github.com/sarammu7-bot/new-emailapp.git'
        GIT_BRANCH = 'main'

        // Deployment EC2
        SSH_KEY     = 'deploy-ec2-key'
        DEPLOY_USER = 'ubuntu'
        DEPLOY_HOST = '172.31.21.92'

        // Production folder
        APP_DIR     = '/home/ubuntu/emailapp'
    }

    stages {

        stage('Checkout Code') {
            steps {
                git branch: "${GIT_BRANCH}",
                    credentialsId: "${GIT_CREDS}",
                    url: "${GIT_REPO}"
            }
        }

        stage('Build Frontend') {
            steps {
                sh '''
                if [ -d frontend ]; then
                    cd frontend
                    npm install
                    npm run build
                else
                    echo "Frontend directory not found, skipping build"
                fi
                '''
            }
        }

        stage('Deploy & Migrate') {
            steps {
                sh """
                set -e

                echo "Copying project to production folder"
                mkdir -p ${APP_DIR}
                rsync -av --delete ${WORKSPACE}/ ${APP_DIR}/ --exclude venv --exclude .git

                cd ${APP_DIR}

                echo "Rebuilding virtual environment"
                python3 -m venv venv
                source venv/bin/activate

                if [ -f requirements.txt ]; then
                    pip install -r requirements.txt
                fi

                echo "Deployment completed successfully"
                """
            }
        }
    }
}

