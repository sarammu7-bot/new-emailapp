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

        // ✅ Permanent production folder
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
                    echo "⚠️ Frontend directory not found, skipping build"
                fi
                '''
            }
        }

        stage('Deploy & Migrate') {
    steps {
        sshagent([env.SSH_KEY]) {
            sh """
            set -e

            echo "📦 Creating production directory on remote"
            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "mkdir -p ${APP_DIR}"

            echo "📦 Syncing files to remote server"
            rsync -avz --delete \
                --exclude '.git' \
                --exclude 'venv' \
                ${WORKSPACE}/ \
                ${DEPLOY_USER}@${DEPLOY_HOST}:${APP_DIR}/

            echo "🔧 Setting up Python environment on remote"
            ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "
                cd ${APP_DIR}
                rm -rf venv
                python3 -m venv venv
                venv/bin/python -m pip install --upgrade pip
                venv/bin/python -m pip install -r requirements.txt
                venv/bin/python manage.py migrate
            "
            """
        }
    }
}



        stage('Restart Services') {
            steps {
                sshagent([env.SSH_KEY]) {
                    sh """
                    ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} "
                        sudo systemctl daemon-reload
                        sudo systemctl restart fastapi
                        sudo systemctl restart nginx
                    "
                    """
                }
            }
        }
    }

    post {
        success {
            echo '✅ stackly-email deployed successfully'
        }
        failure {
            echo '❌ Deployment failed – check stage logs'
        }
    }
}
