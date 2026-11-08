data "aws_route53_zone" "socialops" {
  name         = var.domain_name
  private_zone = false
}

resource "aws_acm_certificate" "socialops" {
  domain_name       = "*.${var.domain_name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "acm_validation" {
  allow_overwrite = true
  zone_id         = data.aws_route53_zone.socialops.zone_id
  name            = tolist(aws_acm_certificate.socialops.domain_validation_options)[0].resource_record_name
  type            = tolist(aws_acm_certificate.socialops.domain_validation_options)[0].resource_record_type
  ttl             = 300
  records         = [tolist(aws_acm_certificate.socialops.domain_validation_options)[0].resource_record_value]
}

resource "aws_acm_certificate_validation" "socialops" {
  certificate_arn         = aws_acm_certificate.socialops.arn
  validation_record_fqdns = [aws_route53_record.acm_validation.fqdn]
}

resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.socialops.zone_id
  name    = local.web_hostname
  type    = "A"

  alias {
    name                   = module.alb.dns_name
    zone_id                = module.alb.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.socialops.zone_id
  name    = local.api_hostname
  type    = "A"

  alias {
    name                   = module.alb.dns_name
    zone_id                = module.alb.zone_id
    evaluate_target_health = true
  }
}
