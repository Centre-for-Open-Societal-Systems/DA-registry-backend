// DA Registry (OpenG2P) -- CI pipeline.
//
// BUILD AND PUSH ONLY. There is deliberately no Deploy stage yet: the DA
// registry's namespace, hostnames, kubeconfig credential and shared commons
// services are still to be confirmed with DevOps. The farmer pipeline this was
// derived from deploys into the `far` namespace with farmer credentials; that
// stage was removed so a DA build can never touch the farmer deployment.
// Add a Deploy stage here once the DA namespace and credential exist.
pipeline {
    agent any

    environment {
        AWS_ACCOUNT_ID = "${env.AWS_ACCOUNT_ID}"
        AWS_REGION     = "ap-south-1"
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        ECR_PATH       = "openg2p/da-registry"

        // Must match ARG RP_VERSION / STAFF_UI_VERSION in the root Dockerfile
        // and the openg2p-registry dependency in helm/openg2p-da-registry/Chart.yaml.
        // The staff UI is built from the same registry-platform run.
        RP_VERSION     = "1.2.2-rc.544"

        HELM_CHART_DIR = "helm/openg2p-da-registry"
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('ECR Login') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds']]) {
                    sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                }
            }
        }

        stage('Build & Push') {
            steps {
                script {
                    env.IMAGE_TAG = env.GIT_COMMIT.take(12)

                    // Build the root Dockerfile's targets, the same definition
                    // docker compose builds, so CI ships what developers run.
                    def components = [
                        [name: 'staff-api',   target: 'staff-api',   args: "--build-arg RP_VERSION=${RP_VERSION}"],
                        [name: 'staff-ui',    target: 'staff-ui',    args: "--build-arg STAFF_UI_VERSION=${RP_VERSION}"],
                        [name: 'partner-api', target: 'partner-api', args: "--build-arg RP_VERSION=${RP_VERSION}"],
                        [name: 'celery',      target: 'celery',      args: "--build-arg RP_VERSION=${RP_VERSION}"],
                        [name: 'db-seed',     target: 'db-seed',     args: "--build-arg RP_VERSION=${RP_VERSION}"],
                    ]

                    // Each environment branch also moves a tag of its own name.
                    def movingTag = (env.BRANCH_NAME in ['develop', 'staging', 'main']) ? env.BRANCH_NAME : null
                    components.each { c ->
                        def image  = "${ECR_REGISTRY}/${ECR_PATH}/${c.name}:${env.IMAGE_TAG}"
                        def latest = movingTag ? "${ECR_REGISTRY}/${ECR_PATH}/${c.name}:${movingTag}" : null
                        sh """
                            docker build ${c.args} --target ${c.target} \
                                -f Dockerfile -t ${image} ${latest ? "-t ${latest}" : ''} .
                            docker push ${image}
                            ${latest ? "docker push ${latest}" : ''}
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
            sh "docker logout ${ECR_REGISTRY} || true"
        }
    }
}
