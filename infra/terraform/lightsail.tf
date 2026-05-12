################################################################################
# Lightsail
#
# Single-VM production environment in ap-southeast-2a:
#
#   instance     jeromelu        ubuntu_22_04, small_3_2 ($12/mo)
#   static IP    jeromelu-ip     attached to the instance (52.65.91.199)
#   firewall     22 (operator), 80, 443 (public)
#
# Out of scope for Terraform (intentional):
#   - SSH key pair `jeromelu-prod`. Lightsail keypairs do not round-trip
#     through import cleanly (the public_key attribute is write-only). The
#     key was created via console; private half lives at ~/.ssh/jeromelu-prod
#     on the operator workstation. If we ever need to rotate, do it via
#     console and update the operator's local key file.
#   - Static IP and its attachment to the instance. AWS provider 5.x does
#     not support `terraform import` for `aws_lightsail_static_ip` (or its
#     attachment). The IP exists in AWS, attached to the instance; we read
#     it via `data "aws_lightsail_static_ip"` for downstream references.
#   - cloud-init `user_data`. Already executed at first boot; subsequent edits
#     would be no-ops at best and reprovision-the-host at worst.
#   - Snapshots. Taken weekly via console.
#   - Anything inside the VM (Docker, /opt/jeromelu, /etc/cron.d/...) — that
#     is Compose's territory.
#
# `aws_lightsail_instance_public_ports` also can't be imported, but it can
# be created — the AWS API call is idempotent (`PutInstancePublicPorts`
# replaces the full port set), so creating the resource against an instance
# that already has the exact same ports configured is a no-op. After the
# first apply it lives in state and is managed normally.
################################################################################

resource "aws_lightsail_instance" "jeromelu" {
  name              = "jeromelu"
  availability_zone = "${var.aws_region}a"
  blueprint_id      = "ubuntu_22_04"
  bundle_id         = "small_3_2"
  key_pair_name     = "jeromelu-prod"

  lifecycle {
    ignore_changes = [
      user_data,    # cloud-init already ran
      blueprint_id, # blueprints rev frequently; don't reprovision the host
    ]
  }
}

resource "aws_lightsail_instance_public_ports" "jeromelu" {
  instance_name = aws_lightsail_instance.jeromelu.name

  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
    cidrs     = [var.operator_ssh_cidr]
  }

  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
    cidrs     = ["0.0.0.0/0"]
  }

  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
    cidrs     = ["0.0.0.0/0"]
  }
}
